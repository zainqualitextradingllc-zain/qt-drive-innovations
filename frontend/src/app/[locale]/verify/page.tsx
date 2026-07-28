import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/routing";
import { VerifyAnalytics } from "@/components/VerifyAnalytics";
import { verifyAttestation } from "@/lib/api";
import type { Locale } from "@/types/diagnosis";

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ h?: string }>;
};

const VEHICLE_PLACEHOLDERS = new Set([
  "",
  "unknown",
  "n/a",
  "na",
  "none",
  "null",
  "undefined",
  "not specified",
  "not provided",
  "unspecified",
  "不明",
  "なし",
  "未設定",
]);

function isRealVehiclePart(x: unknown): boolean {
  if (x === null || x === undefined) return false;
  if (typeof x === "number") return x >= 1980 && x <= 2100;
  const s = String(x).trim();
  if (!s) return false;
  if (VEHICLE_PLACEHOLDERS.has(s.toLowerCase())) return false;
  // year-like string "0" or "0000"
  if (/^\d+$/.test(s)) {
    const n = parseInt(s, 10);
    return n >= 1980 && n <= 2100;
  }
  return true;
}

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
  const parts = [v.year, v.make, v.model, v.engine].filter(isRealVehiclePart);
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
        <VerifyAnalytics contentHash="" result="missing_hash" />
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
  const analyticsResult =
    error || !data ? "not_found" : valid ? "match" : "mismatch";
  const onChain = data?.on_chain;
  const onChainConfirmed = Boolean(onChain?.anchored && onChain?.tx_hash);

  return (
    <main className="verify-page">
      <VerifyAnalytics contentHash={hash} result={analyticsResult} />
      <div className="verify-card">
        <h1>{t("title")}</h1>
        <p className="verify-sub">{t("subtitle")}</p>

        {error || !data ? (
          <div className="verify-banner verify-fail" role="status">
            {t("notFound")}
          </div>
        ) : (
          <>
            {/* Layer 1: immediate integrity (SHA-256) — independent of chain */}
            <section className="verify-status-layer" aria-label={t("integrityLabel")}>
              <h2 className="verify-layer-title">{t("integrityLabel")}</h2>
              <div
                className={`verify-banner ${valid ? "verify-ok" : "verify-fail"}`}
                role="status"
              >
                {valid ? t("integrityOk") : t("integrityFail")}
              </div>
              <p className="verify-layer-detail">
                {valid ? t("valid") : t("invalid")}
              </p>
            </section>

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

            {/* Layer 2: on-chain (daily batch) — pending is expected, not an error */}
            <section
              className="verify-status-layer verify-onchain-layer"
              aria-label={t("onChainLabel")}
            >
              <h2 className="verify-layer-title">{t("onChainLabel")}</h2>
              <div
                className={`verify-onchain-badge ${
                  onChainConfirmed ? "verify-onchain-ok" : "verify-onchain-pending"
                }`}
                role="status"
              >
                <span className="verify-onchain-label">
                  {onChainConfirmed ? "⛓️ " : "⏳ "}
                  {onChainConfirmed ? t("onChainConfirmed") : t("onChainPending")}
                </span>
                {onChainConfirmed && onChain?.explorer_url ? (
                  <a
                    className="verify-explorer-link"
                    href={onChain.explorer_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("viewOnExplorer")}
                  </a>
                ) : null}
                {!onChainConfirmed ? (
                  <p className="verify-onchain-hint">{t("onChainPendingHint")}</p>
                ) : null}
                {onChainConfirmed ? (
                  <details className="verify-tech-details">
                    <summary>{t("techDetails")}</summary>
                    <dl className="verify-dl verify-tech-dl">
                      {onChain?.chain_name ? (
                        <div>
                          <dt>{t("chainName")}</dt>
                          <dd>{onChain.chain_name}</dd>
                        </div>
                      ) : null}
                      {onChain?.block_number != null ? (
                        <div>
                          <dt>{t("blockNumber")}</dt>
                          <dd>{String(onChain.block_number)}</dd>
                        </div>
                      ) : null}
                      {onChain?.tx_hash ? (
                        <div className="verify-hash-row">
                          <dt>Tx</dt>
                          <dd className="mono-hash">{onChain.tx_hash}</dd>
                        </div>
                      ) : null}
                      {onChain?.merkle_root ? (
                        <div className="verify-hash-row">
                          <dt>{t("merkleRoot")}</dt>
                          <dd className="mono-hash">{onChain.merkle_root}</dd>
                        </div>
                      ) : null}
                      {onChain?.leaf_hash ? (
                        <div className="verify-hash-row">
                          <dt>{t("leafHash")}</dt>
                          <dd className="mono-hash">{onChain.leaf_hash}</dd>
                        </div>
                      ) : null}
                      {onChain?.proof && onChain.proof.length > 0 ? (
                        <div className="verify-hash-row">
                          <dt>{t("merkleProof")}</dt>
                          <dd className="mono-hash">
                            {onChain.proof.join("\n")}
                          </dd>
                        </div>
                      ) : null}
                    </dl>
                  </details>
                ) : null}
              </div>
            </section>
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
