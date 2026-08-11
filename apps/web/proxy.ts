import { NextRequest, NextResponse } from "next/server";
import { isLocale } from "./lib/i18n";

export function proxy(request: NextRequest) {
  const segments = request.nextUrl.pathname.split("/").filter(Boolean);
  const routeLocale = isLocale(segments[0]) ? segments[0] : undefined;
  const cookieLocale = request.cookies.get("carevero-locale")?.value;
  const locale = routeLocale ?? (isLocale(cookieLocale) ? cookieLocale : "en");
  const headers = new Headers(request.headers);
  headers.set("x-carevero-locale", locale);
  if (!routeLocale) return NextResponse.next({ request: { headers } });

  const url = request.nextUrl.clone();
  url.pathname = `/${segments.slice(1).join("/")}`;
  return NextResponse.rewrite(url, { request: { headers } });
}

export const config = {
  matcher: ["/((?!_next|api|brand|.*\\..*).*)"],
};
