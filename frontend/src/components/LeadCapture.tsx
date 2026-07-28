"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { captureLead } from "@/lib/api";
import { captureEvent } from "@/lib/posthog";
import { verifyUrl } from "@/lib/verifyUrl";
import type { Locale, SeverityCode } from "@/types/diagnosis";

type Props = {
  sessionId: string;
  locale: Locale;
  diagnosisCategory: string;
  contentHash?: string | null;
  /** When stop_immediately, auto-open the quote form (high-intent). */
  severityCode?: SeverityCode | string | null;
};

export function LeadCapture({
  sessionId,
  locale,
  diagnosisCategory,
  contentHash = null,
  severityCode = null,
}: Props) {
  const t = useTranslations("lead");
  const isUrgent = severityCode === "stop_immediately";
  const [method, setMethod] = useState<"email" | "line">("email");
  const [value, setValue] = useState("");
  // High-severity: form open by default (no extra click to expand)
  const [open, setOpen] = useState(isUrgent);
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
      severity_code: severityCode || "",
      auto_opened: isUrgent,
    });
    // Analytics only on mount for this diagnosis card instance
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fire once on mount
  }, []);

  function onCtaClick() {
    captureEvent("cta_clicked", {
      session_id: sessionId,
      cta_type: method,
      diagnosis_category: diagnosisCategory,
      severity_code: severityCode || "",
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

  const promptText = isUrgent ? t("promptUrgent") : t("prompt");
  const shellClass = [
    "lead-capture",
    isUrgent ? "lead-urgent" : "",
    done ? "lead-success" : "",
    open && !done ? "lead-form" : "",
  ]
    .filter(Boolean)
    .join(" ");

  if (done) {
    // Optional verify blurb after success (primary verify link lives on DiagnosisCard)
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
      <div className={shellClass} role="status">
        <p className="lead-success-main">{t("success")}</p>
        {verifyParts ? <p className="lead-verify-blurb">{verifyParts}</p> : null}
      </div>
    );
  }

  if (!open) {
    return (
      <div className={shellClass}>
        <p className="lead-prompt">{promptText}</p>
        <button type="button" className="btn btn-primary lead-cta" onClick={onCtaClick}>
          {t("cta")}
        </button>
      </div>
    );
  }

  return (
    <form className={shellClass} onSubmit={onSubmit}>
      <p className="lead-prompt">{promptText}</p>
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
        autoFocus={isUrgent}
      />
      {error ? <div className="lead-error">{error}</div> : null}
      <button className="btn btn-primary" type="submit" disabled={loading || !value.trim()}>
        {loading ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
