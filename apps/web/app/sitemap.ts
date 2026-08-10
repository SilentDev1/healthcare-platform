import type { MetadataRoute } from "next";
import { apiGet, type FacilityPage, type Procedure } from "../lib/api";
import { launchRegion } from "../lib/brand";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  const core = [
    "",
    "/hospitals",
    "/procedures",
    "/map",
    "/about-data",
    "/how-it-works",
  ];
  let dynamic: string[] = [];
  try {
    const [facilities, procedures] = await Promise.all([
      apiGet<FacilityPage>(
        `/api/v1/facilities?state=${launchRegion.state}&page_size=100`,
      ),
      apiGet<{ items: Procedure[] }>("/api/v1/procedures?page_size=100"),
    ]);
    dynamic = [
      ...facilities.items.map((item) => `/hospitals/${item.id}`),
      ...procedures.items.map((item) => `/procedures/${item.slug}`),
    ];
  } catch {}
  return [...core, ...dynamic].map((path) => ({
    url: `${base}${path}`,
    changeFrequency: path === "" ? "weekly" : "daily",
    priority: path === "" ? 1 : path.split("/").length > 2 ? 0.6 : 0.7,
  }));
}
