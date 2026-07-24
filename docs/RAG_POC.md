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
| CSV import (non-technical) | `backend/scripts/import_knowledge_csv.py` + `backend/data/knowledge_import_template.csv` |
| Quality tests | `backend/scripts/test_rag_quality.py` |

**Table name:** `public.knowledge_entries` (this is the knowledge base).  
Embeddings: OpenAI `text-embedding-3-small` → `vector(1536)`.

---

## 1. Hard-quoted costs

When a **strong** RAG hit exists, cost is **not** left to GPT:

1. Prompt includes `[MANDATORY COST QUOTE]` with exact `estimated_cost` / `cost_min` / `cost_max`.
2. On `emit_diagnosis`, the server **overwrites** those fields via `apply_grounded_cost()`.

Example: knowledge `150–400 USD` → UI must show `150-400 USD`, even if the model said `200-600 USD`.

---

## 2. Similarity threshold

| Setting | Default | Env |
|---------|---------|-----|
| `rag_min_similarity` | **0.55** | `RAG_MIN_SIMILARITY` |

- Vector hit with `similarity >= 0.55` → **strong** → inject grounding + hard cost.
- Below threshold → **dropped** → prompt says no strong match → general GPT knowledge.
- Exact **OBD code** matches always count as strong (even without a similarity score).
- Pure text-token fallbacks without a vector score are **not** strong.

Example: Japanese battery query ~**0.560** → **above** 0.55 → strong match.

Tune in Railway / `.env`: `RAG_MIN_SIMILARITY=0.55`

---

## 3. Multilingual retrieval

Each knowledge row is **bilingual** (`title_en`/`title_ja`, causes, severity, costs, `embed_text` with EN+JA tokens).  
`text-embedding-3-small` maps Japanese queries into the same space as English titles (verified: JP battery query → “Battery no-crank”).

You do **not** need separate tables per language; keep EN+JA fields filled on each row for best recall.

---

## 4. Server-side debug logs

Logger name: `qt.rag`  
Each chat turn logs (Railway / uvicorn stdout only — **not** user-facing):

```text
rag_retrieve session_id=... min_sim=0.55 strong=1/3 query='brakes grinding' hits=[{title, sim, source, strong}, ...]
```

---

## 5. Fallback (unknown symptoms)

If nothing is strong, the context block says:

`[GROUNDED KNOWLEDGE] none retrieved … use general diagnostic knowledge`

No fake catalog match is forced. GPT may still answer as a technician without claiming KB grounding.

---

## 6. How to add new issues (non-technical)

**Easiest path: send a CSV** (or fill the template and ask the team to run the import).

1. Copy `backend/data/knowledge_import_template.csv`
2. Add rows (one issue per row). Use `;` between multiple causes.
3. Developer runs:

```bash
cd backend
python scripts/import_knowledge_csv.py data/your_issues.csv
python scripts/import_knowledge_csv.py data/your_issues.csv --dry-run   # preview only
```

That inserts missing `title_en` rows and embeds them. No redeploy required for new knowledge (shared Supabase DB).

---

## Chat flow

1. Embed user message  
2. Retrieve top-k → **filter strong**  
3. Log retrieval  
4. Inject strong snippets + mandatory cost quote  
5. GPT responds; on diagnosis, **server overwrites cost** from top strong hit  

No change to CORS, Vercel routing, or frontend structure.

---

## Commands

```bash
cd backend
python scripts/ingest_knowledge_poc.py --test-only
python scripts/test_rag_quality.py
python scripts/import_knowledge_csv.py data/knowledge_import_template.csv --dry-run
```
