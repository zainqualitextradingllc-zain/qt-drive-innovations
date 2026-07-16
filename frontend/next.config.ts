import type { NextConfig } from "next";
import path from "path";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname),
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "i0.wp.com",
      },
      {
        protocol: "https",
        hostname: "www.qualitex-trading.com",
      },
    ],
  },
  // Allow WordPress (qualitex-trading.com) to embed this app in an iframe.
  // Modern browsers use CSP frame-ancestors; X-Frame-Options ALLOW-FROM is obsolete
  // and is omitted so it cannot conflict with CSP.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value:
              "frame-ancestors 'self' https://qualitex-trading.com https://www.qualitex-trading.com https://*.qualitex-trading.com;",
          },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
