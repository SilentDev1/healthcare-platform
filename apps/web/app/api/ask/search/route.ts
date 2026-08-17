import { NextRequest, NextResponse } from "next/server";

// Same-origin server-side proxy for grounded deterministic search results.
// Read-only: only the whitelisted q/state params are forwarded upstream.
const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim() ?? "";
  const state = (req.nextUrl.searchParams.get("state") ?? "NH").toUpperCase();
  if (!q) return NextResponse.json({ items: [], capability_locations: [] });
  const params = new URLSearchParams({ q, state });
  try {
    const upstream = await fetch(`${API_URL}/api/v1/search?${params}`, {
      cache: "no-store",
    });
    const data = await upstream
      .json()
      .catch(() => ({ items: [], capability_locations: [] }));
    return NextResponse.json(data, { status: upstream.ok ? 200 : upstream.status });
  } catch {
    return NextResponse.json(
      { items: [], capability_locations: [] },
      { status: 502 },
    );
  }
}
