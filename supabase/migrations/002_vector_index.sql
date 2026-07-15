-- ============================================================
-- Run AFTER seed data + embedding backfill
-- (ivfflat is weak/useless on empty or all-null embedding columns)
-- ============================================================

-- Optional: HNSW is often better for smaller/medium datasets on modern pgvector
-- create index if not exists knowledge_entries_embedding_hnsw
--   on public.knowledge_entries
--   using hnsw (embedding vector_cosine_ops);

create index if not exists knowledge_entries_embedding_idx
  on public.knowledge_entries
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);
