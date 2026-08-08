"""RAG service — bridges the Data/RAG layer into the FastAPI backend.

Architecture:
  FastAPI → rag_service.retrieve_context()
          → Data/RAG curriculum_vector_db.query_vector_db()
          → ChromaDB (TF-IDF)
          → ranked curriculum chunks

This module is intentionally thin.  All heavy RAG logic lives in Data/RAG/.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path wiring: add Data/RAG to sys.path so we can import its modules.
# ---------------------------------------------------------------------------

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent   # backend/
_PROJECT_ROOT = _BACKEND_ROOT.parent                            # AB-Talks-ai_interview_Platform/
_RAG_ROOT = _PROJECT_ROOT / "Data" / "RAG"                      # Data/RAG/
_RAG_APP_ROOT = _RAG_ROOT / "app"                               # Data/RAG/app/

if str(_RAG_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_RAG_APP_ROOT))
if str(_RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(_RAG_ROOT))

# ---------------------------------------------------------------------------
# Lazy-loaded RAG state (loaded once on first use, not at import time)
# ---------------------------------------------------------------------------

_state: dict[str, Any] = {
    "collection": None,
    "candidates": {},     # candidate_id -> raw profile dict
    "knowledge_maps": {}, # candidate_id -> CandidateKnowledgeMap
    "loaded": False,
}

_RAG_DATA_DIR = _RAG_ROOT / "data"
_RAG_STORAGE_DIR = _RAG_ROOT / "storage"
_CURRICULUM_PATH = _RAG_DATA_DIR / "curriculum.json"
_CANDIDATES_PATH = _RAG_DATA_DIR / "candidates.json"
_PERSIST_PATH = _RAG_STORAGE_DIR / "rag_pipeline_chroma_db"


def _ensure_loaded() -> bool:
    """Lazily initialise the RAG layer. Returns True if available."""
    if _state["loaded"]:
        return _state["collection"] is not None

    _state["loaded"] = True  # mark so we don't retry on every call

    try:
        import importlib
        candidate_processor = importlib.import_module("candidate_processor")
        rag_pipeline = importlib.import_module("rag_pipeline")
        curriculum_vector_db = importlib.import_module("curriculum_vector_db")

        CandidateKnowledgeMap = candidate_processor.CandidateKnowledgeMap
        process_candidate = candidate_processor.process_candidate
        convert_candidate_profile = rag_pipeline.convert_candidate_profile
        load_curriculum_chunks = rag_pipeline.load_curriculum_chunks
        build_vector_db = curriculum_vector_db.build_vector_db
        query_vector_db = curriculum_vector_db.query_vector_db

        # Store the query function for later use
        _state["query_fn"] = query_vector_db

        # Build or reload vector DB from persisted storage
        curriculum_chunks = load_curriculum_chunks(_CURRICULUM_PATH)
        collection = build_vector_db(curriculum_chunks, _PERSIST_PATH)
        _state["collection"] = collection
        logger.info("RAG: loaded %d curriculum chunks", len(curriculum_chunks))

        # Load all candidates
        with _CANDIDATES_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        for raw_candidate in raw.get("candidates", []):
            profile = convert_candidate_profile(raw_candidate)
            cid = profile.get("candidate_id")
            if cid:
                _state["candidates"][str(cid)] = raw_candidate   # keep raw for frontend
                _state["knowledge_maps"][str(cid)] = process_candidate(profile)

        logger.info("RAG: loaded %d candidates", len(_state["candidates"]))
        return True

    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG unavailable — %s", exc)
        _state["collection"] = None
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_context(
    query: str,
    *,
    curriculum_day: int | None = None,
    topic: str | None = None,
    candidate_id: str | None = None,
    top_k: int = 3,
) -> list[str]:
    """Return curriculum context chunks relevant to *query*.

    Returns an empty list if RAG is unavailable (graceful fallback).
    The returned strings are plain text ready to be embedded in an LLM prompt.
    """
    if not _ensure_loaded():
        return []

    collection = _state["collection"]
    query_fn = _state.get("query_fn")
    if collection is None or query_fn is None:
        return []

    # Build enriched query string using available metadata
    parts = [query]
    if topic:
        parts.append(topic)
    if curriculum_day:
        parts.append(f"day {curriculum_day}")
    enriched_query = " ".join(parts)

    try:
        matches = query_fn(collection, enriched_query, top_k)
        chunks: list[str] = []
        for match in matches:
            text = match.get("text") or match.get("document") or ""
            if text:
                chunks.append(text.strip())
        logger.info(
            "RAG: retrieved %d chunks for query=%r candidate=%s",
            len(chunks), query[:60], candidate_id,
        )
        return chunks
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG query failed — %s", exc)
        return []


def get_candidate_profile(candidate_id: str) -> dict[str, Any] | None:
    """Return the raw candidate dict from candidates.json or None if not found."""
    if not _ensure_loaded():
        return None
    return _state["candidates"].get(str(candidate_id))


def get_all_candidates() -> list[dict[str, Any]]:
    """Return a list of safe candidate summary dicts (no sensitive internal data)."""
    if not _ensure_loaded():
        return []
    results = []
    for raw in _state["candidates"].values():
        member = raw.get("member", {})
        missions = raw.get("missions", [])
        signals = raw.get("signals", {})
        results.append({
            "id": member.get("id"),
            "name": member.get("name"),
            "jobRole": member.get("jobRole"),
            "yearsExperience": member.get("yearsExperience"),
            "education": member.get("education"),
            "status": member.get("status"),
            "missionsCompleted": signals.get("missionsCompleted", 0),
            "commitDays": signals.get("commitDays", 0),
        })
    return results


def get_candidate_weak_topics(candidate_id: str) -> list[str]:
    """Return weak/unknown topics for a candidate (used to focus questions)."""
    if not _ensure_loaded():
        return []
    knowledge_map = _state["knowledge_maps"].get(str(candidate_id))
    if knowledge_map is None:
        return []
    try:
        from rag_pipeline import get_topics_by_label
        return get_topics_by_label(knowledge_map, "weak") + get_topics_by_label(knowledge_map, "unknown")
    except Exception:  # noqa: BLE001
        return []


def get_candidate_knowledge_map(candidate_id: str) -> dict[str, Any] | None:
    """Return the candidate knowledge map in JSONable format."""
    if not _ensure_loaded():
        return None
    knowledge_map = _state["knowledge_maps"].get(str(candidate_id))
    if knowledge_map is None:
        return None
    try:
        from api import to_jsonable
        return to_jsonable(knowledge_map)
    except Exception:  # noqa: BLE001
        return None

