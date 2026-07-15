export type Locale = "en" | "ja";

export type SeverityCode = "safe_to_drive" | "caution" | "stop_immediately";

export interface DiagnosisCause {
  cause: string;
  confidence: number;
  rationale?: string | null;
}

export interface VehicleContext {
  vin?: string | null;
  year?: number | null;
  make?: string | null;
  model?: string | null;
  engine?: string | null;
  source?: "nhtsa_vpic" | "user_reported" | "unknown";
}

export interface DiagnosisPayload {
  language: Locale;
  vehicle_context?: VehicleContext | null;
  diagnosis: DiagnosisCause[];
  severity: string;
  severity_code: SeverityCode;
  estimated_cost: string;
  currency: "USD" | "JPY";
  cost_min?: number | null;
  cost_max?: number | null;
  next_action: string;
  related_obd_codes?: string[];
  questions_asked_count?: number;
  confidence_overall?: number | null;
  assumptions?: string[];
  safety_flags?: string[];
  disclaimer: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  diagnosis?: DiagnosisPayload | null;
}

export interface ChatApiResponse {
  session_id: string;
  language: Locale;
  reply: string;
  mode: "question" | "diagnosis" | "info" | "error";
  vehicle?: VehicleContext | null;
  diagnosis?: DiagnosisPayload | null;
  questions_asked_count: number;
  intent: string;
  rag_hits?: unknown[];
}
