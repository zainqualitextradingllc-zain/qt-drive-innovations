import type { Locale } from "@/types/diagnosis";

/** Public verify page URL for a content hash (locale-aware). Fail-soft: callers must pass a non-empty hash. */
export function verifyUrl(locale: Locale, contentHash: string): string {
  const h = encodeURIComponent(contentHash.trim());
  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}/${locale}/verify?h=${h}`;
  }
  const base =
    process.env.NEXT_PUBLIC_SITE_URL ||
    process.env.NEXT_PUBLIC_VERCEL_URL ||
    "https://qt-drive-innovations.vercel.app";
  const origin = base.startsWith("http") ? base : `https://${base}`;
  return `${origin.replace(/\/$/, "")}/${locale}/verify?h=${h}`;
}
