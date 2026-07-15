-- ============================================================
-- QT Drive Innovations: Bilingual Knowledge Base Schema
-- For Supabase (Postgres + pgvector extension)
-- Run in Supabase SQL Editor (or via supabase db push)
-- ============================================================

-- 1. Enable pgvector extension (required for embeddings/RAG search)
create extension if not exists vector;

-- ============================================================
-- TABLE: knowledge_entries
-- Stores bilingual symptom -> cause -> fix mappings + OBD codes
-- ============================================================
create table if not exists public.knowledge_entries (
  id uuid primary key default gen_random_uuid(),

  -- Classification
  entry_type text not null check (entry_type in ('symptom', 'obd_code', 'general_repair')),
  obd_code text,                          -- e.g. "P0300" (null if not an OBD entry)

  -- Bilingual content (English)
  title_en text not null,
  description_en text not null,
  likely_causes_en text[] not null,
  severity_en text not null,
  recommended_action_en text not null,
  estimated_cost_usd_min integer,
  estimated_cost_usd_max integer,

  -- Bilingual content (Japanese)
  title_ja text not null,
  description_ja text not null,
  likely_causes_ja text[] not null,
  severity_ja text not null,
  recommended_action_ja text not null,
  estimated_cost_jpy_min integer,
  estimated_cost_jpy_max integer,

  -- Vehicle applicability (optional filters)
  applicable_makes text[],
  applicable_min_year integer,
  applicable_max_year integer,

  -- Text used when generating embeddings (EN||JA concatenated for multilingual recall)
  embed_text text,

  -- RAG embedding vector
  -- 1536 dims = OpenAI text-embedding-3-small (adjust if using another model)
  embedding vector(1536),

  -- Metadata
  source text default 'manual',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ============================================================
-- INDEXES (non-vector first — safe on empty tables)
-- ============================================================
create index if not exists idx_knowledge_entries_obd_code
  on public.knowledge_entries (obd_code);

create index if not exists idx_knowledge_entries_type
  on public.knowledge_entries (entry_type);

-- IVFFlat needs rows with non-null embeddings to be useful.
-- Create AFTER seed + embedding backfill (see migration 002 or README).
-- create index if not exists knowledge_entries_embedding_idx
--   on public.knowledge_entries
--   using ivfflat (embedding vector_cosine_ops)
--   with (lists = 100);

-- updated_at trigger
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists knowledge_entries_set_updated_at on public.knowledge_entries;
create trigger knowledge_entries_set_updated_at
  before update on public.knowledge_entries
  for each row execute function public.set_updated_at();

-- ============================================================
-- TABLE: diagnostic_sessions
-- ============================================================
create table if not exists public.diagnostic_sessions (
  id uuid primary key default gen_random_uuid(),
  session_id text unique not null,

  vin text,
  vehicle_make text,
  vehicle_model text,
  vehicle_year integer,
  vehicle_engine text,

  language text not null default 'en' check (language in ('en', 'ja')),
  question_count integer default 0,
  max_questions integer default 4,

  status text default 'active' check (status in ('active', 'diagnosed', 'abandoned')),

  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_diagnostic_sessions_session_id
  on public.diagnostic_sessions (session_id);

drop trigger if exists diagnostic_sessions_set_updated_at on public.diagnostic_sessions;
create trigger diagnostic_sessions_set_updated_at
  before update on public.diagnostic_sessions
  for each row execute function public.set_updated_at();

-- ============================================================
-- TABLE: diagnostic_messages
-- ============================================================
create table if not exists public.diagnostic_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references public.diagnostic_sessions(id) on delete cascade,

  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,

  retrieved_knowledge_ids uuid[],

  created_at timestamptz default now()
);

create index if not exists idx_diagnostic_messages_session
  on public.diagnostic_messages (session_id);

-- ============================================================
-- TABLE: diagnosis_results
-- ============================================================
create table if not exists public.diagnosis_results (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references public.diagnostic_sessions(id) on delete cascade,

  language text not null check (language in ('en', 'ja')),

  diagnosis jsonb not null,

  severity text not null,
  estimated_cost_min integer,
  estimated_cost_max integer,
  currency text default 'USD' check (currency in ('USD', 'JPY')),
  next_action text not null,

  source_knowledge_ids uuid[],

  created_at timestamptz default now()
);

create index if not exists idx_diagnosis_results_session
  on public.diagnosis_results (session_id);

-- ============================================================
-- FUNCTION: match_knowledge_entries
-- Semantic search for RAG (requires non-null embeddings)
-- ============================================================
create or replace function public.match_knowledge_entries (
  query_embedding vector(1536),
  match_threshold float default 0.5,
  match_count int default 5
)
returns table (
  id uuid,
  entry_type text,
  obd_code text,
  title_en text,
  title_ja text,
  description_en text,
  description_ja text,
  likely_causes_en text[],
  likely_causes_ja text[],
  severity_en text,
  severity_ja text,
  recommended_action_en text,
  recommended_action_ja text,
  estimated_cost_usd_min integer,
  estimated_cost_usd_max integer,
  estimated_cost_jpy_min integer,
  estimated_cost_jpy_max integer,
  similarity float
)
language sql
stable
as $$
  select
    ke.id,
    ke.entry_type,
    ke.obd_code,
    ke.title_en,
    ke.title_ja,
    ke.description_en,
    ke.description_ja,
    ke.likely_causes_en,
    ke.likely_causes_ja,
    ke.severity_en,
    ke.severity_ja,
    ke.recommended_action_en,
    ke.recommended_action_ja,
    ke.estimated_cost_usd_min,
    ke.estimated_cost_usd_max,
    ke.estimated_cost_jpy_min,
    ke.estimated_cost_jpy_max,
    1 - (ke.embedding <=> query_embedding) as similarity
  from public.knowledge_entries ke
  where ke.embedding is not null
    and 1 - (ke.embedding <=> query_embedding) > match_threshold
  order by ke.embedding <=> query_embedding
  limit match_count;
$$;

-- Public read for knowledge (optional; service role bypasses RLS)
alter table public.knowledge_entries enable row level security;

drop policy if exists "Allow public read knowledge" on public.knowledge_entries;
create policy "Allow public read knowledge"
  on public.knowledge_entries
  for select
  to anon, authenticated
  using (true);

-- Session tables: enable RLS later when Supabase Auth is wired
-- alter table public.diagnostic_sessions enable row level security;
-- alter table public.diagnostic_messages enable row level security;
-- alter table public.diagnosis_results enable row level security;

comment on table public.knowledge_entries is
  'QT Drive Innovations bilingual OBD/symptom knowledge for RAG grounding';
