import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/routing";
import { verifyAttestation } from "@/lib/api";
import type { Locale } from "@/types/diagnosis";

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ h?: string }>;
};

function vehicleLabel(
  v: {
    year?: number | null;
    make?: string | null;
    model?: string | null;
    engine?: string | null;
  } | null
    | undefined,
  unknown: string
): string {
  if (!v) return unknown;
  const parts = [v.year, v.make, v.model, v.engine].filter(
    (x) => x !== null && x !== undefined && String(x).trim() !== ""
  );
  return parts.length ? parts.join(" ") : unknown;
}

export default async function VerifyPage({ params, searchParams }: Props) {
  const { locale: loc } = await params;
  const locale = loc as Locale;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "verify" });
  const sp = await searchParams;
  const hash = (sp.h || "").trim();

  if (!hash) {
    return (
      <main className="verify-page">
        <div className="verify-card">
          <h1>{t("title")}</h1>
          <p className="verify-sub">{t("subtitle")}</p>
          <p className="verify-warn">{t("missingHash")}</p>
          <Link href="/" className="btn btn-primary">
            {t("backHome")}
          </Link>
        </div>
      </main>
    );
  }

  let error: "notFound" | "network" | null = null;
  let data: Awaited<ReturnType<typeof verifyAttestation>> | null = null;
  try {
    data = await verifyAttestation(hash);
  } catch {
    error = "notFound";
  }

  const valid = Boolean(data?.valid);
  const summary = data?.summary;
  const onChainMsg =
    locale === "ja"
      ? data?.on_chain?.message_ja || t("onChain")
      : data?.on_chain?.message_en || t("onChain");

  return (
    <main className="verify-page">
      <div className="verify-card">
        <h1>{t("title")}</h1>
        <p className="verify-sub">{t("subtitle")}</p>

        {error || !data ? (
          <div className="verify-banner verify-fail" role="status">
            {t("notFound")}
          </div>
        ) : (
          <>
            <div
              className={`verify-banner ${valid ? "verify-ok" : "verify-fail"}`}
              role="status"
            >
              {valid ? t("valid") : t("invalid")}
            </div>

            <dl className="verify-dl">
              <div>
                <dt>{t("vehicle")}</dt>
                <dd>{vehicleLabel(summary?.vehicle, t("unknownVehicle"))}</dd>
              </div>
              <div>
                <dt>{t("topCause")}</dt>
                <dd>{summary?.top_cause || "—"}</dd>
              </div>
              <div>
                <dt>{t("confidence")}</dt>
                <dd>
                  {summary?.top_confidence != null
                    ? `${Math.round(Number(summary.top_confidence))}%`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt>{t("costRange")}</dt>
                <dd>
                  {summary?.cost_min != null && summary?.cost_max != null
                    ? `${summary.cost_min} – ${summary.cost_max}`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt>{t("timestamp")}</dt>
                <dd>{summary?.timestamp || data.created_at || "—"}</dd>
              </div>
              <div>
                <dt>{t("model")}</dt>
                <dd>{summary?.model_version || "—"}</dd>
              </div>
              <div className="verify-hash-row">
                <dt>{t("hash")}</dt>
                <dd className="mono-hash">{data.content_hash}</dd>
              </div>
              <div className="verify-hash-row">
                <dt>{t("recomputed")}</dt>
                <dd className="mono-hash">{data.recomputed_hash}</dd>
              </div>
            </dl>

            <p className="verify-onchain">{onChainMsg}</p>
          </>
        )}

        <div className="verify-actions">
          <Link href="/" className="btn btn-primary">
            {t("backHome")}
          </Link>
        </div>
      </div>
    </main>
  );
}
