"""Deterministic curriculum progression for the interview flow."""

from __future__ import annotations

from typing import TypedDict


class CurriculumTopic(TypedDict):
    day: int
    name: str
    description: str


# Derived from backend/data/static_questions.json, which is the only existing
# curriculum source in this repository. Keeping this catalog separate makes a
# future data-backed curriculum replacement local to this module.
CURRICULUM_TOPICS: tuple[CurriculumTopic, ...] = (
    {"day": 1, "name": "Python Fundamentals", "description": "Python programming fundamentals and core data structures."},
    {"day": 2, "name": "Backend REST APIs", "description": "REST API design, HTTP semantics, and backend services."},
    {"day": 3, "name": "Databases", "description": "Data modelling, SQL, indexing, and query performance."},
    {"day": 4, "name": "Security", "description": "Authentication, authorization, and secure backend practices."},
    {"day": 5, "name": "Production Observability", "description": "Diagnosing, monitoring, and improving production services."},
)


def covered_topic_names(history: list[dict]) -> set[str]:
    """Return topics whose assigned question has been answered."""
    return {item["curriculum_topic"] for item in history if item.get("answer") is not None}


TOPIC_KEYWORDS = {
    "Python Fundamentals": ["python", "fundamentals", "environment", "basics", "setup"],
    "Backend REST APIs": ["api", "rest", "fastapi", "http", "route", "backend"],
    "Databases": ["database", "db", "sql", "index", "vector", "embedding", "query", "retrieval", "search"],
    "Security": ["security", "auth", "encrypt", "token", "jwt", "key", "deployment", "docker", "kubernetes"],
    "Production Observability": ["observability", "monitor", "log", "metric", "trace", "diagnose", "agent", "mcp", "protocol", "orchestration"]
}


def next_topic(history: list[dict], candidate_id: str | None = None) -> tuple[CurriculumTopic, str]:
    """Decide next topic adaptive pathway: (topic_dict, pathway_type).

    Pathway types:
      - 'primary': Brand new module topic.
      - 'follow_up': Deeper exploration because candidate answered well.
      - 'clarification': Foundational questions due to weak/incorrect response.
    """
    if not history:
        # For the first question, if candidate_id has weak topics, start with one of those if possible
        prioritized = list(CURRICULUM_TOPICS)
        if candidate_id:
            try:
                from app.services.rag_service import get_candidate_weak_topics
                weak_topics = get_candidate_weak_topics(candidate_id)
                if weak_topics:
                    matched_weak = []
                    for t in CURRICULUM_TOPICS:
                        t_lower = t["name"].lower()
                        for wt in weak_topics:
                            wt_lower = wt.lower()
                            if any(kw in wt_lower for kw in TOPIC_KEYWORDS[t["name"]]):
                                matched_weak.append(t)
                                break
                    if matched_weak:
                        prioritized = matched_weak + [t for t in CURRICULUM_TOPICS if t not in matched_weak]
            except Exception:
                pass
        return prioritized[0], "primary"

    last_item = history[-1]
    last_eval = last_item.get("evaluation")
    
    # Analyze evaluation scores for adaptive pathway choice
    score = last_eval.get("score") if last_eval else None
    
    # If the score is low (< 5), issue a clarification/foundational question on the SAME topic
    if score is not None and score < 5:
        current_topic_name = last_item.get("curriculum_topic")
        matching = [t for t in CURRICULUM_TOPICS if t["name"] == current_topic_name]
        if matching:
            return matching[0], "clarification"

    # If the score is decent but not perfect (5-7), issue a follow-up on the SAME topic
    if score is not None and score <= 7:
        current_topic_name = last_item.get("curriculum_topic")
        matching = [t for t in CURRICULUM_TOPICS if t["name"] == current_topic_name]
        if matching:
            return matching[0], "follow_up"

    # Otherwise, progress to the next module
    covered = covered_topic_names(history)
    
    # Prioritize weak/unknown areas for this candidate
    prioritized_topics = list(CURRICULUM_TOPICS)
    if candidate_id:
        try:
            from app.services.rag_service import get_candidate_weak_topics
            weak_topics = get_candidate_weak_topics(candidate_id)
            if weak_topics:
                matched_weak_names = set()
                for wt in weak_topics:
                    wt_lower = wt.lower()
                    for topic_name, keywords in TOPIC_KEYWORDS.items():
                        if any(kw in wt_lower for kw in keywords):
                            matched_weak_names.add(topic_name)
                weak_matched = [t for t in CURRICULUM_TOPICS if t["name"] in matched_weak_names]
                other_topics = [t for t in CURRICULUM_TOPICS if t["name"] not in matched_weak_names]
                prioritized_topics = weak_matched + other_topics
        except Exception:
            pass

    for topic in prioritized_topics:
        if topic["name"] not in covered:
            return topic, "primary"

    # Fallback to last topic as follow_up
    current_topic_name = last_item.get("curriculum_topic")
    matching = [t for t in CURRICULUM_TOPICS if t["name"] == current_topic_name]
    return (matching[0] if matching else CURRICULUM_TOPICS[0]), "follow_up"


