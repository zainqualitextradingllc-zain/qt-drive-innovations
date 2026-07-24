import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";
import { routing } from "./src/i18n/routing";

const intlMiddleware = createMiddleware(routing);

// Same frame-ancestors policy as next.config.ts headers() — keep iframe embed
// support on middleware-handled redirects/responses (do not remove next.config).
const CSP_FRAME_ANCESTORS =
  "frame-ancestors 'self' https://qualitex-trading.com https://www.qualitex-trading.com https://*.qualitex-trading.com;";

function withFrameHeaders(response: NextResponse): NextResponse {
  response.headers.set("Content-Security-Policy", CSP_FRAME_ANCESTORS);
  return response;
}

function negotiateLocale(request: NextRequest): (typeof routing.locales)[number] {
  const cookie = request.cookies.get("NEXT_LOCALE")?.value;
  if (cookie && routing.locales.includes(cookie as "en" | "ja")) {
    return cookie as "en" | "ja";
  }

  const accept = request.headers.get("accept-language") || "";
  const primary = accept.split(",")[0]?.trim().toLowerCase() || "";
  if (primary.startsWith("ja")) return "ja";

  return routing.defaultLocale;
}

export default function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Bare "/" must never fall through to a missing root page (production 404).
  // Prefer next-intl negotiation; hard-fallback to negotiated/default locale.
  if (pathname === "/") {
    const intlResponse = intlMiddleware(request);
    if (intlResponse instanceof NextResponse) {
      const location = intlResponse.headers.get("location");
      if (location) {
        return withFrameHeaders(intlResponse);
      }
    }

    const url = request.nextUrl.clone();
    url.pathname = `/${negotiateLocale(request)}`;
    return withFrameHeaders(NextResponse.redirect(url));
  }

  const response = intlMiddleware(request);
  if (response instanceof NextResponse) {
    return withFrameHeaders(response);
  }
  return response;
}

export const config = {
  // Root (locale redirect) + localized app routes (header injection on both)
  matcher: ["/", "/(en|ja)/:path*"],
};
