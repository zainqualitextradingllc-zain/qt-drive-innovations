# QT Drive Innovations — Bilingual AI Car Diagnostic Assistant

> ⚠️ **Proprietary Software** — See [LICENSE](./LICENSE) for usage terms.
> 
> This is a public repository for collaboration and code review purposes only. 
> "QT Drive Innovations" is a registered trademark of Qualitex Trading LLC.
> No license is granted for commercial use, redistribution, or derivative works.

---

## Project Overview
A bilingual (English/Japanese) AI-powered car diagnostic chat assistant that 
interprets vehicle symptoms, cross-references a curated knowledge base via 
RAG (Retrieval-Augmented Generation), and returns structured diagnosis with 
severity, cost estimates, and recommended actions.

**Stack:** Next.js (frontend) · FastAPI (backend) · Supabase/pgvector (RAG) · OpenAI

---

# QT Drive Innovations

AI-powered car diagnostic assistant (Skill #1) for **Qualitex Trading LLC**.

Bilingual **日本語 / English** · Jarvis-style orchestration scaffold · NHTSA VIN decode · bilingual RAG (Supabase pgvector).

## Monorepo layout

```
qt-drive-innovations/
├── frontend/          # Next.js 15 + next-intl (chat UI, language toggle)
├── backend/           # FastAPI orchestrator + LLM tools
├── supabase/          # Migrations + seed data (bilingual knowledge)
├── .env.example       # All secret placeholders
└── README.md
```

## Prerequisites

- Node.js 20+
- Python 3.11+
- Supabase project (Postgres + pgvector)
- OpenAI API key **or** Google Gemini API key

## 1. Environment keys

```bash
# From repo root
cp .env.example backend/.env
cp .env.example frontend/.env.local
```

Edit both files and replace placeholders:

| Variable | Where | Purpose |
|----------|--------|---------|
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | `backend/.env` | LLM |
| `LLM_PROVIDER` | `backend/.env` | `openai` or `gemini` |
| `SUPABASE_URL` | `backend/.env` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | `backend/.env` | Server-side RAG |
| `DATABASE_URL` | optional | Direct SQL |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | Backend base URL (default `http://localhost:8000`) |

## 2. Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. Open **SQL Editor** and run in order:
   1. `supabase/migrations/001_knowledge_base.sql` — schema + `match_knowledge_entries` RPC  
      (pgvector, `knowledge_entries`, sessions/messages/results tables)
   2. `supabase/seed/seed_knowledge.sql` — bilingual sample rows (embeddings null)
   3. **After** embedding backfill: `supabase/migrations/002_vector_index.sql` (ivfflat)
3. Put project URL + **service role** key in `backend/.env`.

> Do **not** run `002_vector_index.sql` before embeddings exist — IVFFlat needs non-null vectors.

## 3. Backend (FastAPI)

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Health: http://localhost:8000/health  
- Docs: http://localhost:8000/docs  

## 4. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 — default locale redirects to `/en` or `/ja`.

## Architecture

```
Browser (next-intl)
    │  language + chat messages
    ▼
FastAPI Orchestrator
    ├─ route_intent (car_diagnostics | future skills)
    ├─ decode_vin → NHTSA vPIC (free, no key)
    ├─ search_repair_knowledge → Supabase pgvector
    └─ LLM (OpenAI / Gemini) + emit_diagnosis tool
```

### Conversation flow

0. Language tab (JP / EN)  
1. Optional VIN → NHTSA decode  
2. Primary symptom  
3. Up to 3–4 clarifying questions (one at a time)  
4. Structured diagnosis (causes, severity, cost, next action)

## Brand

- **QT Drive Innovations** · parent: Qualitex Trading LLC  
- Logo: dark charcoal, chrome QT monogram, red accent  
- UI theme matches night-cockpit automotive aesthetic  

## Trademark / disclaimer

AI estimates are informational only and do not replace professional inspection or emergency services.

## Embedding backfill (pgvector RAG)

After Supabase migration + seed, fill `knowledge_entries.embedding`:

```powershell
cd C:\Users\zain_\qt-drive-innovations\backend
.\.venv\Scripts\activate

# Preview rows that need embeddings (no API cost)
python scripts/backfill_embeddings.py --dry-run

# Write embeddings (needs real OPENAI_API_KEY + Supabase service role)
python scripts/backfill_embeddings.py --verify "brakes grinding"
python scripts/backfill_embeddings.py --verify "ブレーキ きしむ"

# Re-run verify only
python scripts/backfill_embeddings.py --verify-only --verify "P0300"
```

Then create the vector index in SQL Editor:

```text
supabase/migrations/002_vector_index.sql
```

Chat path: when OpenAI + Supabase are configured, the orchestrator embeds each user message and calls `match_knowledge_entries` (falls back to text/code match and local offline rows if needed).

## Next steps after scaffold

1. Plug in API keys  
2. Run Supabase migration + seed  
3. Run embedding backfill  
4. Start backend + frontend with `USE_MOCK_LLM=false`  
5. Expand OBD knowledge seed  
6. Deploy: Vercel (frontend) + Railway/Render (backend)  
