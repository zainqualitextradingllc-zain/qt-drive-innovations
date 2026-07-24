# RAG Proof-of-Concept — Knowledge Base

## What exists

| Piece | Location |
|-------|----------|
| Schema + pgvector + `match_knowledge_entries` | `supabase/migrations/001_knowledge_base.sql` |
| IVFFlat index (after embeddings) | `supabase/migrations/002_vector_index.sql` |
| Seed SQL (10 bilingual issues) | `supabase/seed/seed_knowledge.sql` |
| OpenAI embed helpers | `backend/app/services/embeddings.py` |
| Vector / code / text search | `backend/app/tools/rag.py` |
| Inject into system prompt before GPT | `backend/app/services/orchestrator.py` |
| PoC ingest + retrieval tests | `backend/scripts/ingest_knowledge_poc.py` |

**Table name:** `public.knowledge_entries` (this is the knowledge base).  
Embeddings: OpenAI `text-embedding-3-small` → `vector(1536)`.

## Chat flow (already wired)

1. Embed user message (`embed_query`)
2. `search_repair_knowledge` → top-k hits (Postgres RPC preferred)
3. `hits_to_prompt_snippets` → `[GROUNDED KNOWLEDGE]` block in system prompt
4. GPT answers with tool calling as before

No change to CORS, Vercel routing, or frontend chat structure.

## Run the PoC (local)

```bash
cd backend
# .env needs DATABASE_URL + OPENAI_API_KEY
python scripts/ingest_knowledge_poc.py
python scripts/ingest_knowledge_poc.py --test-only
python scripts/ingest_knowledge_poc.py --status
```

Upserts any of the 10 sample docs missing by `title_en`, embeds rows with null embeddings, then runs retrieval smoke tests.

## Sample issues (10)

1. Grinding noise when braking  
2. P0300 misfire  
3. P0420 catalyst  
4. Engine overheating with steam  
5. Battery no-crank / click only  
6. Brake pedal sinks to floor  
7. AC blows warm air only  
8. Car pulls to one side when braking  
9. P0171 system too lean  
10. Transmission slips or delayed engagement  

## Ops notes

- Run migration `001` once in Supabase SQL Editor if the table is missing.
- After first full embed, optionally run `002_vector_index.sql`.
- Railway needs `DATABASE_URL` (or Supabase service role) + `OPENAI_API_KEY` for live RAG.
