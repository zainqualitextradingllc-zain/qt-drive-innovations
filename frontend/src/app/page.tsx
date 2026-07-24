import { redirect } from "next/navigation";

/**
 * Root "/" fallback — if middleware is skipped (CDN static 404 cache, edge
 * miss), this page still sends users into a locale prefix.
 * Prefer English as the embed/default landing; users can toggle JA in UI.
 */
export default function RootPage() {
  redirect("/en");
}
