import type { ChatApiResponse, Locale, VehicleContext } from "@/types/diagnosis";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function sendChatMessage(params: {
  message: string;
  language: Locale;
  sessionId?: string | null;
  vehicle?: VehicleContext | null;
}): Promise<ChatApiResponse> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: params.message,
      language: params.language,
      session_id: params.sessionId || undefined,
      vehicle: params.vehicle || undefined,
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }

  return res.json();
}

export async function checkHealth(): Promise<{ status: string; use_mock_llm?: boolean }> {
  const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error("health failed");
  return res.json();
}

export { API_URL };
