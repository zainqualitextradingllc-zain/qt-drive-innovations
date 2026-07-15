"use client";

import { useTranslations } from "next-intl";
import { LanguageToggle } from "./LanguageToggle";

const LOGO_URL =
  "https://i0.wp.com/www.qualitex-trading.com/wp-content/uploads/2025/06/c9855e7e-9e9d-45c4-9627-97108e5b3c22_0-1_Nero_AI_Image_Upscaler_Photo_Face-modified-1.png?ssl=1";

export function Navbar() {
  const t = useTranslations();

  return (
    <header className="navbar">
      <div className="navbar-top">
        <div className="brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={LOGO_URL}
            alt="QT Drive Innovations"
            className="brand-logo"
            width={42}
            height={42}
          />
          <div className="brand-text">
            <div className="brand-name">{t("brand.name")}</div>
            <div className="brand-tagline">{t("brand.tagline")}</div>
          </div>
        </div>
        <LanguageToggle />
      </div>
      <div className="navbar-meta">
        <span className="skill-pill">{t("nav.diagnostics")}</span>
        <span>{t("nav.skillsSoon")}</span>
      </div>
    </header>
  );
}
