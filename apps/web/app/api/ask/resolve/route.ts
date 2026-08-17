import { NextRequest, NextResponse } from "next/server";

// Same-origin server-side proxy for the Ask Carevero medical/scope gate.
// Keeping this server-side means the browser never calls the API cross-origin
// (works on any web origin, in any browser, and never exposes the API URL).
const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  let body: { message?: unknown; locale?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }
  const message = typeof body.message === "string" ? body.message : "";
  const locale = typeof body.locale === "string" ? body.locale : "en";
  if (!message.trim()) {
    return NextResponse.json({ error: "empty_message" }, { status: 400 });
  }
  try {
    const upstream = await fetch(`${API_URL}/api/v1/ai/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, locale }),
      cache: "no-store",
    });
    const data = await upstream.json().catch(() => null);
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    // Upstream unreachable — let the client fall through to its deterministic path.
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 502 });
  }
}
