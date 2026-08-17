import { NextRequest, NextResponse } from "next/server";

// Same-origin server-side proxy for grounded deterministic search results.
// Read-only: only the whitelisted q/locale params are forwarded upstream.
// NOTE: procedures are global (not state-scoped) so we do NOT forward `state`
// to /search — passing it filters procedures out. Region scoping happens on
// the price/comparison endpoints instead.
const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

const LOCALES = new Set(["en", "es", "vi", "zh-TW", "zh-CN"]);

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim() ?? "";
  const localeParam = req.nextUrl.searchParams.get("locale") ?? "en";
  const locale = LOCALES.has(localeParam) ? localeParam : "en";
  if (!q) return NextResponse.json({ items: [], capability_locations: [] });
  const params = new URLSearchParams({ q, locale, page_size: "8" });
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
