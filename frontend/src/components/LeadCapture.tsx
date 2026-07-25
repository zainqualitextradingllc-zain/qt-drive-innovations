"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { captureLead } from "@/lib/api";
import { captureEvent } from "@/lib/posthog";
import type { Locale } from "@/types/diagnosis";

type Props = {
  sessionId: string;
  locale: Locale;
  diagnosisCategory: string;
  contentHash?: string | null;
};

function verifyUrl(locale: Locale, contentHash: string): string {
  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}/${locale}/verify?h=${encodeURIComponent(contentHash)}`;
  }
  const base =
    process.env.NEXT_PUBLIC_SITE_URL ||
    process.env.NEXT_PUBLIC_VERCEL_URL ||
    "https://qt-drive-innovations.vercel.app";
  const origin = base.startsWith("http") ? base : `https://${base}`;
  return `${origin.replace(/\/$/, "")}/${locale}/verify?h=${encodeURIComponent(contentHash)}`;
}

export function LeadCapture({
  sessionId,
  locale,
  diagnosisCategory,
  contentHash = null,
}: Props) {
  const t = useTranslations("lead");
  const [method, setMethod] = useState<"email" | "line">("email");
  const [value, setValue] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const verifyLink = useMemo(
    () => (contentHash ? verifyUrl(locale, contentHash) : null),
    [contentHash, locale]
  );

  useEffect(() => {
    captureEvent("cta_shown", {
      session_id: sessionId,
      cta_type: "email",
      diagnosis_category: diagnosisCategory,
      has_content_hash: Boolean(contentHash),
    });
  }, [sessionId, diagnosisCategory, contentHash]);

  function onCtaClick() {
    captureEvent("cta_clicked", {
      session_id: sessionId,
      cta_type: method,
      diagnosis_category: diagnosisCategory,
    });
    setOpen(true);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const contact = value.trim();
    if (!contact || loading) return;

    setLoading(true);
    setError(null);
    try {
      await captureLead({
        sessionId,
        contactMethod: method,
        diagnosisCategory,
        locale,
        contactValue: contact,
      });
      // lead_captured is fired server-side (source of truth)
      setDone(true);
    } catch {
      setError(t("error"));
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    // Exact EN/JA copy with <url></url> rich placeholder for the verify link
    const verifyParts = verifyLink
      ? t.rich("verifyBlurb", {
          url: () => (
            <a href={verifyLink} target="_blank" rel="noopener noreferrer">
              {verifyLink}
            </a>
          ),
        })
      : null;

    return (
      <div className="lead-capture lead-success" role="status">
        <p className="lead-success-main">{t("success")}</p>
        {verifyParts ? <p className="lead-verify-blurb">{verifyParts}</p> : null}
      </div>
    );
  }

  if (!open) {
    return (
      <div className="lead-capture">
        <p className="lead-prompt">{t("prompt")}</p>
        <button type="button" className="btn btn-primary lead-cta" onClick={onCtaClick}>
          {t("cta")}
        </button>
      </div>
    );
  }

  return (
    <form className="lead-capture lead-form" onSubmit={onSubmit}>
      <p className="lead-prompt">{t("prompt")}</p>
      <div className="lead-method-row" role="group" aria-label={t("methodLabel")}>
        <button
          type="button"
          className={`btn-ghost ${method === "email" ? "active" : ""}`}
          onClick={() => setMethod("email")}
        >
          {t("email")}
        </button>
        <button
          type="button"
          className={`btn-ghost ${method === "line" ? "active" : ""}`}
          onClick={() => setMethod("line")}
        >
          {t("line")}
        </button>
      </div>
      <input
        type={method === "email" ? "email" : "text"}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={method === "email" ? t("emailPlaceholder") : t("linePlaceholder")}
        disabled={loading}
        required
        autoComplete={method === "email" ? "email" : "off"}
        aria-label={method === "email" ? t("email") : t("line")}
      />
      {error ? <div className="lead-error">{error}</div> : null}
      <button className="btn btn-primary" type="submit" disabled={loading || !value.trim()}>
        {loading ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
