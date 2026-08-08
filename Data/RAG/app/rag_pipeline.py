from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .candidate_processor import CandidateKnowledgeMap, process_candidate
    from .curriculum_extractor import extract_daily_topics
except ImportError:
    from candidate_processor import CandidateKnowledgeMap, process_candidate
    from curriculum_extractor import extract_daily_topics

try:
    from .vector_store_chromadb import build_vector_db, query_vector_db
except ImportError:
    try:
        from .curriculum_vector_db import build_vector_db, query_vector_db
    except ImportError:
        from curriculum_vector_db import build_vector_db, query_vector_db


BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / "data"
STORAGE_DIR = BACKEND_ROOT / "storage"
DEFAULT_CANDIDATES_PATH = DATA_DIR / "candidates.json"
DEFAULT_CURRICULUM_PATH = DATA_DIR / "curriculum.json"
DEFAULT_RAG_STORAGE_PATH = STORAGE_DIR / "rag_pipeline_chroma_db"


@dataclass
class PersonalizedRetrieval:
    focus_topic: str
    reason: str
    matched_chunks: list[dict[str, Any]]


def build_personalized_retrievals(
    knowledge_map: CandidateKnowledgeMap,
    collection: Any,
    top_k: int = 3,
) -> list[PersonalizedRetrieval]:
    retrievals: list[PersonalizedRetrieval] = []

    for label in ["weak", "unknown"]:
        for topic in get_topics_by_label(knowledge_map, label):
            matches = query_vector_db(collection, topic, top_k)
            retrievals.append(
                PersonalizedRetrieval(
                    focus_topic=topic,
                    reason=label,
                    matched_chunks=matches,
                )
            )

    return retrievals


def get_topics_by_label(knowledge_map: CandidateKnowledgeMap, label: str) -> list[str]:
    topics_by_label = getattr(knowledge_map, "topics_by_label", None)
    if callable(topics_by_label):
        return list(topics_by_label(label))

    buckets = getattr(knowledge_map, "buckets", {})
    if isinstance(buckets, dict):
        return list(buckets.get(label, []))

    return [
        topic.topic
        for topic in getattr(knowledge_map, "topics", [])
        if getattr(topic, "label", None) == label
    ]


def load_sample_candidate(path: str | Path = DEFAULT_CANDIDATES_PATH) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("No candidates found in candidates.json.")

    return convert_candidate_profile(candidates[-1])


def convert_candidate_profile(candidate: dict[str, Any]) -> dict[str, Any]:
    member = candidate.get("member", {})
    mission_history = []

    for mission in candidate.get("missions", []):
        mission_history.append(
            {
                "mission_id": f"day-{mission.get('day')}",
                "topic": mission.get("title"),
                "score": mission_score(mission),
                "attempts": mission.get("attempts", 0),
                "status": mission_status(mission),
            }
        )

    return {
        "candidate_id": member.get("id"),
        "candidate_name": member.get("name"),
        "mission_history": mission_history,
    }


def mission_score(mission: dict[str, Any]) -> float | None:
    if mission.get("skipped"):
        return None
    if mission.get("passed") is False:
        return 0.0
    if mission.get("passed") is True:
        return 0.95 if mission.get("attempts", 0) <= 1 else 0.75
    return mission.get("score")


def mission_status(mission: dict[str, Any]) -> str:
    if mission.get("skipped"):
        return "skipped"
    if mission.get("status"):
        return str(mission["status"]).lower()
    return "completed"


def load_curriculum_chunks(
    path: str | Path = DEFAULT_CURRICULUM_PATH,
) -> list[dict[str, Any]]:
    extracted_days = extract_daily_topics(path)
    chunks = []

    for day in extracted_days:
        if "day" not in day:
            continue

        topic = day.get("topic")
        topics = [topic] if topic else []

        chunks.append(
            {
                "chunk_id": f"day-{day['day']}",
                "module_id": day.get("module_number"),
                "module_title": day.get("module_title"),
                "day": day.get("day"),
                "topics": topics,
                "learning_objectives": day.get("learning_objectives", []),
                "tools": day.get("tools", []),
            }
        )

    return chunks


def print_retrievals(retrievals: list[PersonalizedRetrieval]) -> None:
    for retrieval in retrievals:
        print(f"Focus topic: {retrieval.focus_topic}")
        print(f"Reason: {retrieval.reason}")

        for rank, match in enumerate(retrieval.matched_chunks, start=1):
            metadata = match.get("metadata", {})
            print(
                f"  {rank}. score={match.get('score'):.4f} "
                f"chunk={match.get('chunk_id')} "
                f"day={metadata.get('day')} "
                f"module={metadata.get('module_id')} - {metadata.get('module_title')}"
            )
            print(f"     {first_line(match.get('text', ''))}")

        print()


def first_line(text: str) -> str:
    return text.splitlines()[0] if text else ""


if __name__ == "__main__":
    candidate_profile = load_sample_candidate(DEFAULT_CANDIDATES_PATH)
    knowledge_map = process_candidate(candidate_profile)

    curriculum_chunks = load_curriculum_chunks(DEFAULT_CURRICULUM_PATH)
    collection = build_vector_db(curriculum_chunks, DEFAULT_RAG_STORAGE_PATH)

    retrievals = build_personalized_retrievals(
        knowledge_map=knowledge_map,
        collection=collection,
        top_k=3,
    )

    print(f"Candidate: {candidate_profile.get('candidate_id')}")
    print(
        "Weak/unknown topics: "
        + ", ".join(
            get_topics_by_label(knowledge_map, "weak")
            + get_topics_by_label(knowledge_map, "unknown")
        )
    )
    print()
    print_retrievals(retrievals)
