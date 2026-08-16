"""Layered OpenAI Responses API diagnosis — runs server-side, NEVER prints the key.

Reads OPENAI_API_KEY from the environment (mounted from Secret Manager) and probes the
Responses API in escalating layers to isolate whether an HTTP 400 comes from model
access/auth or from a specific request parameter our adapter sends. Prints only sanitized
status codes, OpenAI error type/code/message, org/project response headers, and whether
the target models are listed — never the key.

Run in the deployed env:
  gcloud run jobs execute carevero-beta-price-audit --args="-m,scripts.diagnose_openai"
"""

from __future__ import annotations

import json
import os

import httpx

BASE = "https://api.openai.com/v1"
PRIMARY = os.environ.get("AI_PRIMARY_MODEL", "gpt-5.6-luna")
ESCALATION = os.environ.get("AI_ESCALATION_MODEL", "gpt-5.6-terra")

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
}


def _key_category(key: str) -> str:
    if key.startswith("sk-proj-"):
        return "project-scoped (sk-proj-)"
    if key.startswith("sk-svcacct-"):
        return "service-account (sk-svcacct-)"
    if key.startswith("sk-"):
        return "user/legacy (sk-)"
    return "unknown-prefix"


def _sanitized_error(resp: httpx.Response) -> dict[str, object]:
    out: dict[str, object] = {"status": resp.status_code}
    for header in ("openai-organization", "openai-project", "x-request-id"):
        if header in resp.headers:
            out[header] = resp.headers[header]
    try:
        body = resp.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            out["error_type"] = err.get("type")
            out["error_code"] = err.get("code")
            out["error_param"] = err.get("param")
            msg = err.get("message")
            if isinstance(msg, str):
                out["error_message"] = msg[:240]
    except Exception:
        out["error_message"] = resp.text[:240]
    return out


def _post(client: httpx.Client, payload: dict[str, object]) -> dict[str, object]:
    try:
        resp = client.post(f"{BASE}/responses", json=payload, timeout=30)
    except Exception as exc:  # network/timeout
        return {"status": "EXCEPTION", "error_type": type(exc).__name__}
    result: dict[str, object] = {"status": resp.status_code, "ok": resp.status_code == 200}
    if resp.status_code != 200:
        result.update(_sanitized_error(resp))
    return result


def _layers(client: httpx.Client, model: str) -> dict[str, object]:
    """Escalating payloads; the first layer that flips to non-200 is the culprit."""
    layers: dict[str, dict[str, object]] = {
        "L1_minimal": {"model": model, "input": "Respond with OK"},
        "L2_max_tokens": {"model": model, "input": "Respond with OK", "max_output_tokens": 16},
        "L3_temperature0": {
            "model": model,
            "input": "Respond with OK",
            "max_output_tokens": 16,
            "temperature": 0,
        },
        "L4_store_false": {
            "model": model,
            "input": "Respond with OK",
            "max_output_tokens": 16,
            "temperature": 0,
            "store": False,
        },
        "L5_system_array": {
            "model": model,
            "input": [
                {"role": "system", "content": "You are a test."},
                {"role": "user", "content": "Respond with OK"},
            ],
            "max_output_tokens": 16,
            "temperature": 0,
            "store": False,
        },
        "L6_structured": {
            "model": model,
            "input": [
                {"role": "system", "content": "You are a test."},
                {"role": "user", "content": "Respond with OK"},
            ],
            "max_output_tokens": 16,
            "temperature": 0,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "probe",
                    "strict": True,
                    "schema": _SCHEMA,
                }
            },
        },
    }
    return {name: _post(client, payload) for name, payload in layers.items()}


def main() -> None:
    key = os.environ.get("OPENAI_API_KEY")
    report: dict[str, object] = {
        "secret_present": bool(key),
        "key_length": len(key) if key else 0,
        "key_category": _key_category(key) if key else None,
        "primary_model": PRIMARY,
        "escalation_model": ESCALATION,
    }
    if not key:
        print("OPENAI_DIAGNOSIS=" + json.dumps(report, separators=(",", ":")))
        return

    client = httpx.Client(headers={"authorization": f"Bearer {key}"})

    # Model listing (does auth work? are Luna/Terra visible to this key/project?)
    try:
        models_resp = client.get(f"{BASE}/models", timeout=30)
        report["models_list_status"] = models_resp.status_code
        for header in ("openai-organization", "openai-project"):
            if header in models_resp.headers:
                report[header] = models_resp.headers[header]
        if models_resp.status_code == 200:
            data = models_resp.json().get("data", [])
            ids = sorted(str(m.get("id")) for m in data if isinstance(m, dict))
            report["models_total"] = len(ids)
            report["primary_listed"] = PRIMARY in ids
            report["escalation_listed"] = ESCALATION in ids
            report["gpt5_models_sample"] = [i for i in ids if "gpt-5" in i][:12]
        else:
            report["models_list_error"] = _sanitized_error(models_resp)
    except Exception as exc:
        report["models_list_status"] = "EXCEPTION"
        report["models_list_error"] = type(exc).__name__

    report["primary_layers"] = _layers(client, PRIMARY)
    report["escalation_layers"] = _layers(client, ESCALATION)
    client.close()

    print("OPENAI_DIAGNOSIS=" + json.dumps(report, separators=(",", ":"), default=str))


if __name__ == "__main__":
    main()
