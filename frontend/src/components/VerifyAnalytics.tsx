"use client";

import { useEffect, useRef } from "react";
import { captureEvent } from "@/lib/posthog";

type Result = "match" | "not_found" | "mismatch" | "missing_hash";

/**
 * Fires diagnosis_verify_viewed once per mount (does not touch lead_captured).
 */
export function VerifyAnalytics({
  contentHash,
  result,
}: {
  contentHash: string;
  result: Result;
}) {
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    const prefix = (contentHash || "").slice(0, 8);
    captureEvent("diagnosis_verify_viewed", {
      content_hash_prefix: prefix || null,
      result,
    });
  }, [contentHash, result]);

  return null;
}
