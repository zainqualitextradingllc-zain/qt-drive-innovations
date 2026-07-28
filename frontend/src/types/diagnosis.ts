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
  contentHash?: string | null;
  diagnosisId?: string | null;
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
  /** Phase 4a.0 SHA-256 of PII-free canonical diagnosis JSON */
  content_hash?: string | null;
  diagnosis_id?: string | null;
}

export interface AttestationVerifyResponse {
  found: boolean;
  valid: boolean;
  content_hash: string;
  recomputed_hash: string;
  diagnosis_id?: string;
  session_id?: string;
  created_at?: string | null;
  anchor_status?: string;
  chain_id?: string | null;
  tx_hash?: string | null;
  summary: {
    locale?: string;
    timestamp?: string;
    model_version?: string;
    vehicle?: {
      year?: number | null;
      make?: string | null;
      model?: string | null;
      engine?: string | null;
    };
    top_cause?: string | null;
    top_confidence?: number | null;
    cost_min?: number | null;
    cost_max?: number | null;
    causes?: { cause: string; confidence: number }[];
  };
  on_chain?: {
    anchored: boolean;
    status?: "confirmed" | "pending" | string;
    message_en: string;
    message_ja: string;
    tx_hash?: string | null;
    explorer_url?: string | null;
    merkle_root?: string | null;
    proof?: string[] | null;
    leaf_hash?: string | null;
    leaf_index?: number | null;
    batch_id?: string | null;
    chain_name?: string | null;
    chain_id?: number | string | null;
    block_number?: number | null;
    contract_address?: string | null;
    anchored_at?: string | null;
  };
}
