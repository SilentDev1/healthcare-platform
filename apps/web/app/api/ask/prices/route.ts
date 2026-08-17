import { NextRequest, NextResponse } from "next/server";

// Same-origin server-side proxy for a few REAL price rows for one procedure.
// Prices are always the deterministic API's published summaries — never model output.
const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

// Guard: slug must look like a real procedure slug (lowercase, digits, hyphens).
const SLUG_RE = /^[a-z0-9-]{2,80}$/;

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const slug = req.nextUrl.searchParams.get("slug")?.trim() ?? "";
  const state = (req.nextUrl.searchParams.get("state") ?? "NH").toUpperCase();
  const pageSize = Math.min(
    Math.max(Number(req.nextUrl.searchParams.get("page_size") ?? 4) || 4, 1),
    10,
  );
  if (!SLUG_RE.test(slug)) {
    return NextResponse.json({ items: [] }, { status: 400 });
  }
  const params = new URLSearchParams({ state, page_size: String(pageSize) });
  try {
    const upstream = await fetch(
      `${API_URL}/api/v1/procedures/${encodeURIComponent(slug)}/prices?${params}`,
      { cache: "no-store" },
    );
    const data = await upstream.json().catch(() => ({ items: [] }));
    return NextResponse.json(data, { status: upstream.ok ? 200 : upstream.status });
  } catch {
    return NextResponse.json({ items: [] }, { status: 502 });
  }
}
