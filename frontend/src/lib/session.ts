/** Stable anonymous analytics session id (not PII). Survives reloads within the tab. */

const STORAGE_KEY = "diag_session_id";

export function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = sessionStorage.getItem(STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(STORAGE_KEY, id);
  }
  return id;
}

/** Force a new analytics + chat session (New session button). */
export function resetSessionId(): string {
  if (typeof window === "undefined") return "";
  const id = crypto.randomUUID();
  sessionStorage.setItem(STORAGE_KEY, id);
  return id;
}
