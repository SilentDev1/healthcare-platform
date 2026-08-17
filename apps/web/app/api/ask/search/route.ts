import { NextRequest, NextResponse } from "next/server";

// Same-origin server-side proxy for grounded deterministic search results.
// Read-only: only the whitelisted q/locale params are forwarded upstream.
// NOTE: procedures are global (not state-scoped) so we do NOT forward `state`
// to /search — passing it filters procedures out. Region scoping happens on
// the price/comparison endpoints instead.
const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

const LOCALES = new Set(["en", "es", "vi", "zh-TW", "zh-CN"]);

// Conversational filler that hides the real search term. Stripping it lets a
// natural-language question ("How much is an MRI near Nashua?") fall back to the
// keyword search ("MRI Nashua") when the verbose form finds nothing. Multilingual
// so the retry helps es/vi/zh questions too; the deterministic index itself keys
// on English procedure names/aliases.
const FILLER = new Set([
  // en
  "how", "much", "is", "are", "a", "an", "the", "of", "to", "in", "on", "for",
  "where", "can", "i", "get", "find", "near", "me", "what", "does", "do", "cost",
  "costs", "price", "prices", "priced", "pricing", "compare", "comparison",
  "show", "list", "which", "who", "cheapest", "cheap", "at", "and", "or",
  "please", "help",
  // es
  "cuánto", "cuanto", "cuesta", "precio", "precios", "dónde", "donde", "puedo",
  "cerca", "de", "la", "el", "los", "las", "comparar",
  // vi
  "giá", "bao", "nhiêu", "ở", "gần", "tôi", "so", "sánh", "chỗ", "nào", "của",
  // zh handled by leaving CJK tokens intact
]);

function keywordize(raw: string): string {
  const cleaned = raw
    .toLowerCase()
    .replace(/[?？.!,;:¿"']/g, " ")
    .split(/\s+/)
    .filter((w) => w && !FILLER.has(w));
  return cleaned.join(" ").trim();
}

async function search(q: string, locale: string) {
  const params = new URLSearchParams({ q, locale, page_size: "8" });
  const upstream = await fetch(`${API_URL}/api/v1/search?${params}`, {
    cache: "no-store",
  });
  const data = await upstream
    .json()
    .catch(() => ({ items: [], capability_locations: [] }));
  return { data, ok: upstream.ok, status: upstream.status };
}

function isEmpty(d: { items?: unknown[]; capability_locations?: unknown[] }): boolean {
  return !(d.items?.length || d.capability_locations?.length);
}

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim() ?? "";
  const localeParam = req.nextUrl.searchParams.get("locale") ?? "en";
  const locale = LOCALES.has(localeParam) ? localeParam : "en";
  if (!q) return NextResponse.json({ items: [], capability_locations: [] });
  try {
    const first = await search(q, locale);
    // Second pass: strip conversational filler and retry once if nothing matched.
    if (isEmpty(first.data)) {
      const kw = keywordize(q);
      if (kw && kw !== q.toLowerCase()) {
        const second = await search(kw, locale);
        if (!isEmpty(second.data)) {
          return NextResponse.json(second.data, { status: 200 });
        }
      }
    }
    return NextResponse.json(first.data, {
      status: first.ok ? 200 : first.status,
    });
  } catch {
    return NextResponse.json(
      { items: [], capability_locations: [] },
      { status: 502 },
    );
  }
}
