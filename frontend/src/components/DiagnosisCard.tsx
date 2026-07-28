"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import type { DiagnosisPayload, Locale } from "@/types/diagnosis";
import { verifyUrl } from "@/lib/verifyUrl";
import { LeadCapture } from "./LeadCapture";

export function DiagnosisCard({
  diagnosis,
  sessionId,
  locale,
  diagnosisCategory,
  showLead = false,
  contentHash = null,
}: {
  diagnosis: DiagnosisPayload;
  sessionId: string;
  locale: Locale;
  diagnosisCategory: string;
  showLead?: boolean;
  contentHash?: string | null;
}) {
  const t = useTranslations();
  const code = diagnosis.severity_code;
  const hash = (contentHash || "").trim();
  const verifyHref = useMemo(
    () => (hash ? verifyUrl(locale, hash) : null),
    [hash, locale]
  );

  return (
    <article className={`diagnosis-card severity-${code}`}>
      <div className="diagnosis-header">
        <h3>{t("diagnosis.title")}</h3>
        <span className={`severity-badge ${code}`}>{t(`severity.${code}`)}</span>
      </div>
      <div className="diagnosis-body">
        <div>
          <div className="meta-block" style={{ marginBottom: "0.5rem" }}>
            <label>{t("diagnosis.causes")}</label>
          </div>
          {diagnosis.diagnosis.map((c) => (
            <div className="cause-row" key={c.cause}>
              <div className="cause-top">
                <span>{c.cause}</span>
                <span>
                  {t("diagnosis.confidence")} {Math.round(c.confidence)}%
                </span>
              </div>
              <div className="bar" aria-hidden>
                <i style={{ width: `${Math.min(100, Math.max(0, c.confidence))}%` }} />
              </div>
            </div>
          ))}
        </div>

        <div className="meta-block">
          <label>{t("diagnosis.cost")}</label>
          <div>{diagnosis.estimated_cost}</div>
        </div>

        {/* Visible generic-cost banner when vehicle was skipped / unknown */}
        {(() => {
          const cost = (diagnosis.estimated_cost || "").toLowerCase();
          const disc = (diagnosis.disclaimer || "").toLowerCase();
          const isGeneric =
            cost.includes("generic") ||
            cost.includes("一般") ||
            disc.includes("generic") ||
            disc.includes("一般的な目安") ||
            disc.includes("cost range is generic");
          if (!isGeneric) return null;
          return (
            <div className="cost-generic-banner" role="note">
              {locale === "ja"
                ? "費用は一般的な目安です。メーカー・車種・年式があると精度が上がります。"
                : "Cost range is generic — provide vehicle make/model/year for a more accurate estimate."}
            </div>
          );
        })()}

        <div className="meta-block">
          <label>{t("diagnosis.nextAction")}</label>
          <div>{diagnosis.next_action}</div>
        </div>

        {diagnosis.related_obd_codes && diagnosis.related_obd_codes.length > 0 ? (
          <div className="meta-block">
            <label>{t("diagnosis.obd")}</label>
            <div>{diagnosis.related_obd_codes.join(", ")}</div>
          </div>
        ) : null}

        {/* Fail-soft: only when content_hash is present — never gated on lead form */}
        {verifyHref ? (
          <div className="meta-block integrity-hash diagnosis-verify-block">
            <label>{t("diagnosis.integrityHash")}</label>
            <div className="mono-hash" title={hash}>
              {hash.slice(0, 12)}…{hash.slice(-8)}
            </div>
            <a
              className="btn btn-ghost diagnosis-verify-link"
              href={verifyHref}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t("diagnosis.verifyThisDiagnosis")}
            </a>
            <p className="diagnosis-verify-hint">{t("diagnosis.verifyHint")}</p>
          </div>
        ) : null}

        <p className="disclaimer">{diagnosis.disclaimer || t("footer.disclaimer")}</p>

        {showLead && sessionId ? (
          <LeadCapture
            sessionId={sessionId}
            locale={locale}
            diagnosisCategory={diagnosisCategory}
            contentHash={contentHash}
            severityCode={code}
          />
        ) : null}
      </div>
    </article>
  );
}
