"""Conservative tracked-file secret scan for CI and release gates."""

import re
import subprocess
from pathlib import Path

PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "GitHub token": re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "service account key": re.compile(r'"private_key"\s*:\s*"-----BEGIN'),
}


def main() -> None:
    files = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
    findings: list[str] = []
    for raw in files:
        if not raw:
            continue
        path = Path(raw.decode())
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path}: {label}")
    if findings:
        raise SystemExit("potential secrets found:\n" + "\n".join(findings))
    print("secret scan: PASS")


if __name__ == "__main__":
    main()
