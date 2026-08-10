import type { NextConfig } from "next";
const apiOrigin = process.env.API_PUBLIC_URL ?? "http://localhost:8000";
const deployed = ["beta", "production"].includes(
  process.env.APP_ENV ?? "local",
);
const config: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  agentRules: false,
  async headers() {
    const headers = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "X-Frame-Options", value: "DENY" },
      {
        key: "Permissions-Policy",
        value: "camera=(), microphone=(), geolocation=()",
      },
      {
        key: "Content-Security-Policy",
        value: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.tile.openstreetmap.org; connect-src 'self' ${apiOrigin}; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'`,
      },
    ];
    if (deployed)
      headers.push({
        key: "Strict-Transport-Security",
        value: "max-age=31536000; includeSubDomains",
      });
    return [{ source: "/(.*)", headers }];
  },
};
export default config;
