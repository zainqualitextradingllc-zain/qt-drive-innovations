import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { Navbar } from "@/components/Navbar";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const title =
    locale === "ja"
      ? "QT Drive Innovations — 診断アシスタント"
      : "QT Drive Innovations — Diagnostic Assistant";
  return {
    title,
    description:
      locale === "ja"
        ? "AI車両診断アシスタント（Qualitex Trading LLC）"
        : "AI car diagnostic assistant by Qualitex Trading LLC",
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as "en" | "ja")) {
    notFound();
  }

  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider messages={messages}>
          <div className="app-shell">
            <Navbar />
            {children}
            <footer className="footer-bar">
              <div>
                {locale === "ja"
                  ? "本結果は情報提供を目的としたAI推定であり、専門整備の代替ではありません。"
                  : "AI estimate for information only — not a substitute for professional inspection."}
              </div>
              <div>© Qualitex Trading LLC · QT Drive Innovations</div>
            </footer>
          </div>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
