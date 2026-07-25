"use client";

import { useTranslations } from "next-intl";
import type { DiagnosisPayload, Locale } from "@/types/diagnosis";
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

        {contentHash ? (
          <div className="meta-block integrity-hash">
            <label>{t("diagnosis.integrityHash")}</label>
            <div className="mono-hash" title={contentHash}>
              {contentHash.slice(0, 12)}…{contentHash.slice(-8)}
            </div>
          </div>
        ) : null}

        <p className="disclaimer">{diagnosis.disclaimer || t("footer.disclaimer")}</p>

        {showLead && sessionId ? (
          <LeadCapture
            sessionId={sessionId}
            locale={locale}
            diagnosisCategory={diagnosisCategory}
            contentHash={contentHash}
          />
        ) : null}
      </div>
    </article>
  );
}
