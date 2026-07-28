-- QT ProofChain™ Phase 4a.1 — mirrored from qt-proofchain/supabase/migrations/001_anchor_batches.sql
-- On-chain Merkle batch metadata + per-hash proofs (no PII).

create table if not exists public.anchor_batches (
  batch_id uuid primary key default gen_random_uuid(),
  merkle_root text not null,
  tx_hash text null,
  block_number bigint null,
  chain_name text not null,
  chain_id integer null,
  contract_address text null,
  created_at timestamptz not null default now(),
  hash_count integer not null check (hash_count >= 0),
  status text not null default 'pending'
    check (status in ('pending', 'submitted', 'confirmed', 'failed')),
  error_message text null,
  interval_hours integer null
);

create index if not exists idx_anchor_batches_created_at
  on public.anchor_batches (created_at desc);

create index if not exists idx_anchor_batches_tx_hash
  on public.anchor_batches (tx_hash);

create index if not exists idx_anchor_batches_merkle_root
  on public.anchor_batches (merkle_root);

create table if not exists public.attestation_merkle_proofs (
  id uuid primary key default gen_random_uuid(),
  content_hash text not null,
  batch_id uuid not null references public.anchor_batches (batch_id) on delete cascade,
  leaf_hash text not null,
  proof jsonb not null default '[]'::jsonb,
  leaf_index integer not null,
  created_at timestamptz not null default now(),
  unique (content_hash, batch_id)
);

create index if not exists idx_attestation_merkle_proofs_content_hash
  on public.attestation_merkle_proofs (content_hash);

create index if not exists idx_attestation_merkle_proofs_batch_id
  on public.attestation_merkle_proofs (batch_id);

create or replace view public.v_attestation_onchain as
select
  p.content_hash,
  p.leaf_hash,
  p.proof,
  p.leaf_index,
  b.batch_id,
  b.merkle_root,
  b.tx_hash,
  b.block_number,
  b.chain_name,
  b.chain_id,
  b.contract_address,
  b.created_at as anchored_at,
  b.status as batch_status
from public.attestation_merkle_proofs p
join public.anchor_batches b on b.batch_id = p.batch_id
where b.status in ('submitted', 'confirmed');
