import posthog from "posthog-js";

let initialized = false;

export function initPostHog(): typeof posthog | null {
  if (typeof window === "undefined") return null;
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  if (!key) return null;

  if (!initialized) {
    posthog.init(key, {
      api_host: "https://us.i.posthog.com",
      person_profiles: "identified_only",
      capture_pageview: false,
      capture_pageleave: false,
    });
    initialized = true;
  }
  return posthog;
}

export function captureEvent(
  event: string,
  properties?: Record<string, string | number | boolean | null | undefined>
): void {
  const ph = initPostHog();
  if (!ph) return;
  ph.capture(event, properties);
}

export function identifyAnonymous(sessionId: string): void {
  const ph = initPostHog();
  if (!ph || !sessionId) return;
  // Anonymous only — never identify with email/LINE
  ph.identify(sessionId);
}

export default posthog;
