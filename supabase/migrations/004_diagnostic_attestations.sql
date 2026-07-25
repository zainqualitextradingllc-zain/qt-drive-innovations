-- Phase 4a.0: SHA-256 diagnosis integrity (no chain yet; chain_id/tx_hash reserved for 4a.1)
create table if not exists public.diagnostic_attestations (
  id uuid primary key default gen_random_uuid(),
  diagnosis_id text not null,
  session_id text not null,
  canonical_json jsonb not null,
  content_hash text not null,
  created_at timestamptz not null default now(),
  chain_id text null,
  tx_hash text null,
  anchor_status text not null default 'hashed'
    check (anchor_status in ('hashed', 'pending_anchor', 'anchored', 'failed'))
);

create unique index if not exists idx_diagnostic_attestations_content_hash
  on public.diagnostic_attestations (content_hash);

create index if not exists idx_diagnostic_attestations_session_id
  on public.diagnostic_attestations (session_id);

create index if not exists idx_diagnostic_attestations_diagnosis_id
  on public.diagnostic_attestations (diagnosis_id);

create index if not exists idx_diagnostic_attestations_created_at
  on public.diagnostic_attestations (created_at desc);

comment on table public.diagnostic_attestations is
  'PII-free diagnosis integrity records. content_hash = SHA-256 of canonical_json. Phase 4a.1 fills chain_id/tx_hash.';
