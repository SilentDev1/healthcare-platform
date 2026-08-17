import { NextRequest, NextResponse } from "next/server";

// Same-origin proxy for the Provider Directory Map view. Server-side so the browser
// never calls the API cross-origin (works on any web origin). Read-only: only the
// whitelisted state/capability/region/pricing_status params are forwarded.
const API_URL = process.env.CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const params = new URLSearchParams();
  params.set("state", (sp.get("state") ?? "NH").toUpperCase().slice(0, 2));
  const capability = sp.get("capability");
  if (capability) params.set("capability", capability.slice(0, 60));
  const region = sp.get("region");
  if (region) params.set("region", region.slice(0, 80));
  const pricing = sp.get("pricing_status");
  if (pricing) params.set("pricing_status", pricing.slice(0, 30));
  try {
    const upstream = await fetch(`${API_URL}/api/v1/facilities/map-data?${params}`, {
      cache: "no-store",
    });
    const data = await upstream
      .json()
      .catch(() => ({ type: "FeatureCollection", features: [] }));
    return NextResponse.json(data, { status: upstream.ok ? 200 : upstream.status });
  } catch {
    return NextResponse.json(
      { type: "FeatureCollection", features: [] },
      { status: 502 },
    );
  }
}
