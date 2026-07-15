import type { ReactNode } from "react";
import "./globals.css";

// Root layout — html/body are rendered in [locale]/layout for lang attribute.
// Next.js requires a root layout file; nested locale layout provides the document shell.
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
