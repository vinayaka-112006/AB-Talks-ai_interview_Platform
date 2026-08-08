from __future__ import annotations

from threading import RLock
from uuid import UUID, uuid4


# Process-local storage: do not run multiple workers until this repository is
# replaced with shared storage such as Redis or PostgreSQL.
_sessions: dict[str, dict] = {}
_lock = RLock()


def create_session(first_question: str, curriculum_topic: dict, candidate_id: str | None = None) -> dict:
    session_id = str(uuid4())
    session = {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "history": [
            {
                "question": first_question,
                "answer": None,
                "curriculum_day": curriculum_topic["day"],
                "curriculum_topic": curriculum_topic["name"],
                "evaluation": None,
            }
        ],
        "question_count": 0,  # Kept for compatibility: completed answers.
        "questions_asked": 1,
        "answers_answered": 0,
        "status": "active",
        "evaluations": {},
    }
    with _lock:
        _sessions[session_id] = session
    return session


def get_session(session_id: str) -> dict | None:
    try:
        UUID(session_id, version=4)
    except (ValueError, TypeError, AttributeError):
        return None
    with _lock:
        return _sessions.get(session_id)


def save_session(session: dict) -> None:
    with _lock:
        _sessions[session["session_id"]] = session
