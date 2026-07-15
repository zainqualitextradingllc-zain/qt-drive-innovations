"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/routing";
import { useTransition } from "react";

export function LanguageToggle() {
  const t = useTranslations("language");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [pending, startTransition] = useTransition();

  const switchTo = (next: "en" | "ja") => {
    if (next === locale) return;
    startTransition(() => {
      router.replace(pathname, { locale: next });
    });
  };

  return (
    <div
      className="lang-toggle"
      role="group"
      aria-label={t("label")}
      data-pending={pending || undefined}
    >
      <button
        type="button"
        className={locale === "ja" ? "active" : undefined}
        onClick={() => switchTo("ja")}
        aria-pressed={locale === "ja"}
      >
        {t("ja")}
      </button>
      <button
        type="button"
        className={locale === "en" ? "active" : undefined}
        onClick={() => switchTo("en")}
        aria-pressed={locale === "en"}
      >
        {t("en")}
      </button>
    </div>
  );
}
