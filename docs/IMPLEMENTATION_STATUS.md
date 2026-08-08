# AI Interview Agent — Implementation Status

> **Audit Date**: 2026-08-08
> **Stage**: 1 — Read-only audit. No code modified.

---

## Component Status Table

| Component | Status | Location | Notes |
|---|---|---|---|
| FastAPI entrypoint | ✅ Working | `backend/app/main.py` | Single router, CORS for localhost:3000 |
| `POST /start-interview` | ✅ Working | `backend/app/routes/interview.py:22` | Returns first hardcoded question; no candidate_id param yet |
| `POST /answer` | ✅ Working | `backend/app/routes/interview.py:33` | Calls `generate_question()` → Ollama → fallback |
| `GET /feedback/{session_id}` | ✅ Working | `backend/app/routes/interview.py:95` | Calls `evaluate_answer()` → Ollama → fallback |
| Session management | ✅ Working | `backend/app/services/session_service.py` | In-memory dict + RLock. Single worker only. |
| Curriculum progression | ✅ Working | `backend/app/services/curriculum_service.py` | 5 hardcoded topics (Day 1–5), covers ≥4 days |
| LLM service | ⚠️ Partial | `backend/app/services/llm_service.py` | Full Ollama integration; falls back silently when unavailable |
| Ollama | 🔴 Unavailable | `http://localhost:11434` | Not running. Manual install in progress. |
| RAG pipeline | ⚠️ Isolated | `Data/RAG/app/rag_pipeline.py` | Fully implemented but NOT connected to FastAPI |
| ChromaDB storage | ✅ Exists | `Data/RAG/storage/` | Two DB dirs: `chroma_curriculum_db/`, `rag_pipeline_chroma_db/` |
| Candidate data | ✅ Exists | `Data/RAG/data/candidates.json` | 20+ candidates (CAND-001+), rich mission history |
| Curriculum data | ✅ Exists | `Data/RAG/data/curriculum.json` | 31-day AI cohort, 8 modules |
| Question bank | ✅ Exists | `Data/RAG/app/question_bank_generator.py` | Generated from curriculum chunks |
| RAG API (standalone) | ✅ Implemented | `Data/RAG/app/api.py` | Separate FastAPI app. NOT wired to main backend. |
| Candidate processor | ✅ Working | `Data/RAG/app/candidate_processor.py` | CandidateKnowledgeMap with strong/weak/unknown buckets |
| Frontend — Launchpad | ✅ Working | `frontend/src/pages/index.js` | Next.js page |
| Frontend — Interview Cockpit | ✅ Working | `frontend/src/pages/interview.js` | 3-zone layout |
| Frontend — Feedback Report | ✅ Working | `frontend/src/pages/feedback.js` | Assessment Intelligence Report |
| Frontend API layer | ✅ Working | `frontend/src/lib/api.js` | Real endpoints + mock fallback |
| Frontend session hook | ⚠️ Partial | `frontend/src/hooks/useInterviewSession.js` | Calls backend; uses MOCK_KNOWLEDGE_MAP for CognitiveMap |
| CognitiveMap | ⚠️ Mock data | `frontend/src/components/CognitiveMap.jsx` | Hardcoded concept IDs, not driven by real backend metadata |
| InterviewJourney | ⚠️ Mock data | `frontend/src/components/InterviewJourney.jsx` | Steps not driven by backend history |
| CandidateSelector | ⚠️ Mock data | `frontend/src/components/CandidateSelector.jsx` | Uses MOCK_CANDIDATES, not candidates.json |
| EvidencePanel | ⚠️ Partial | `frontend/src/components/EvidencePanel.jsx` | UI built; data only from feedback API |
| Light/Dark theme | ✅ Working | `frontend/src/styles/globals.css` | Full toggle working |
| Next.js build | ✅ Passes | `frontend/` | npm run dev on port 3000 |

---

## Architecture Gap Analysis

### Current Actual Architecture

```
FRONTEND (Next.js)
      |
  FastAPI (interview.py)
      |
  LLM Service (llm_service.py)
      |
  Ollama  <--  UNAVAILABLE (FALLBACK ACTIVE)
      |
  Deterministic fallback question
```

### Target Architecture

```
FRONTEND (Next.js)
      |  candidate_id + session_id
  FastAPI (Single Orchestrator)
      |               |
RAG (ChromaDB)    Ollama (LLM)
      |                |
 Context chunks   Grounded question
      |              |
     Adaptive Engine (backend)
            |
     Feedback Engine
```

### What Is Missing

| Missing Feature | Impact | Stage |
|---|---|---|
| Ollama not running | All LLM calls use deterministic fallback | Stage 2 |
| RAG not connected to FastAPI | Questions NOT curriculum-grounded | Stage 3 |
| candidate_id not in /start-interview | No personalization | Stage 4 |
| No adaptive logic | Fixed curriculum rotation only | Stage 5 |
| MAX_QUESTIONS == MIN_QUESTIONS | Interview always ends at exactly 8 | Stage 7 |
| Feedback: per-answer eval only | No holistic strengths/gaps report | Stage 8 |
| CognitiveMap uses mock concept IDs | Not driven by real backend | Stage 9 |
| CandidateSelector uses mock data | Not pulling from candidates.json | Stage 9 |

---

## Key Findings Per Area

### 1. FastAPI Backend
- Entrypoint: `backend/app/main.py` — registers `interview_router`
- Routes: `POST /start-interview`, `POST /answer`, `GET /feedback/{session_id}`, `GET /`
- MIN_QUESTIONS = 8, MAX_QUESTIONS defaults to 8 (same) — always completes at exactly 8
- Completion requires: answers_answered >= 8 AND topics_covered >= 4 AND questions_asked >= MAX_QUESTIONS
- Curriculum: 5 hardcoded topics in `curriculum_service.py` — NOT from curriculum.json

### 2. Ollama / LLM
- Model: llama3 at http://localhost:11434/api/generate
- Timeout: 60s configurable
- generate_question(): last-4-turn context, topic objective in prompt
- evaluate_answer(): JSON-mode eval, score/strength/weakness/suggestion, retries once
- Fallback: "Can you elaborate further on your previous answer?"
- Status: UNAVAILABLE — manual install in progress

### 3. RAG / ChromaDB
- Location: Data/RAG/ — separate from backend/
- Embeddings: TF-IDF (no OpenAI dependency; swap-ready)
- Collection name: "curriculum"
- Storage: Two stores — chroma_curriculum_db/ and rag_pipeline_chroma_db/
- Retrieval: query_vector_db(collection, query_text, top_k)
- Candidate retrieval: focuses on weak/unknown topics per candidate
- Status: FULLY IMPLEMENTED but NOT wired into backend/app/

### 4. Candidate Data
- File: Data/RAG/data/candidates.json
- 20+ candidates: CAND-001 through CAND-020+
- Schema: { member: {id, name, jobRole, yearsExperience, education}, missions: [...], signals: {...} }
- CandidateKnowledgeMap buckets: strong / adequate / weak / unknown / in_progress
- Status: Rich data but NOT sent from frontend to backend

### 5. Curriculum Data
- File: Data/RAG/data/curriculum.json
- 31 days, 8 modules: Environment, Data Foundations, Embeddings, LLM Core, Chatbot, Agentic AI, Security/Deployment, Production
- Backend curriculum_service.py: only 5 short topics (disconnected from real 31-day curriculum)

### 6. Frontend
- api.js: correctly maps snake_case backend -> camelCase frontend
- useInterviewSession: calls backend correctly; still uses MOCK_KNOWLEDGE_MAP for CognitiveMap
- CandidateSelector: reads MOCK_CANDIDATES — not real candidates.json
- TOPIC_CONCEPT_MAP: maps 5 topics to hardcoded concept IDs
- FeedbackReport: 27KB component, reads backend feedback shape correctly

---

## Files That Will Need Changes (Next Stages)

| File | Required Change |
|---|---|
| `backend/app/routes/interview.py` | Accept candidate_id in /start-interview |
| `backend/app/services/curriculum_service.py` | Load from real curriculum.json |
| `backend/app/services/session_service.py` | Store candidate_id, RAG context refs |
| `backend/app/services/llm_service.py` | Accept RAG context in prompt |
| `Data/RAG/app/rag_pipeline.py` | Expose clean retrieve_context() function |
| `frontend/src/lib/api.js` | Pass candidateId to /start-interview |
| `frontend/src/hooks/useInterviewSession.js` | Send real candidate_id; replace MOCK_KNOWLEDGE_MAP |
| `frontend/src/components/CandidateSelector.jsx` | Load from backend /candidates endpoint |

---

## BLOCKER

```
STAGE 2 BLOCKER:
Ollama is NOT running.
ALL questions are currently deterministic fallbacks.
NO real AI generation is happening.

ACTION REQUIRED:
1. Complete Ollama install (user doing manually from https://ollama.com)
2. Run: ollama pull llama3
3. Run: ollama serve
4. Verify: curl http://localhost:11434/api/tags
```
