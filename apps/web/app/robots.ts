import type { MetadataRoute } from "next";
export default function robots(): MetadataRoute.Robots {
  if (process.env.SEO_INDEXING_ENABLED === "false") {
    return { rules: { userAgent: "*", disallow: "/" } };
  }
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/compare", "/search?"],
    },
    sitemap: `${process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"}/sitemap.xml`,
  };
}
