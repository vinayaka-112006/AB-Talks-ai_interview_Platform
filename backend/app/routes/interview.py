import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException

from app.models.schemas import AnswerRequest, AnswerResponse, FeedbackResponse, StartInterviewRequest, StartInterviewResponse
from app.services.curriculum_service import CURRICULUM_TOPICS, covered_topic_names, next_topic
from app.services.llm_service import EvaluationOutcome, evaluate_answer, generate_question
from app.services.session_service import create_session, get_session, save_session


logger = logging.getLogger(__name__)
router = APIRouter(tags=["interview"])
MIN_QUESTIONS = max(8, int(os.getenv("MIN_QUESTIONS", "8")))
MAX_QUESTIONS = max(15, int(os.getenv("MAX_QUESTIONS", "15")))
MIN_CURRICULUM_TOPICS = 4
FIRST_TOPIC = CURRICULUM_TOPICS[0]
FIRST_QUESTION = "Tell me about your Python programming experience and relevant technical work."


@router.post("/start-interview", response_model=StartInterviewResponse)
async def start_interview(request: StartInterviewRequest | None = None) -> StartInterviewResponse:
    cid = request.candidate_id if request else None
    
    initial_topic = FIRST_TOPIC
    initial_question = FIRST_QUESTION
    
    if cid:
        initial_topic, _ = next_topic([], candidate_id=cid)
        if initial_topic != FIRST_TOPIC:
            if initial_topic["name"] == "Backend REST APIs":
                initial_question = "Explain how you design scalable REST APIs, including HTTP status codes and payloads."
            elif initial_topic["name"] == "Databases":
                initial_question = "Describe your experience with databases, data modeling, SQL optimization, or vector search."
            elif initial_topic["name"] == "Security":
                initial_question = "What secure backend development practices, authorization, or authentication systems do you implement?"
            elif initial_topic["name"] == "Production Observability":
                initial_question = "How do you handle production observability, application monitoring, logs, and diagnostics?"

    session = create_session(initial_question, initial_topic, candidate_id=cid)
    return StartInterviewResponse(
        session_id=session["session_id"],
        question=initial_question,
        curriculum_day=initial_topic["day"],
        curriculum_topic=initial_topic["name"],
        candidate_id=cid,
    )



@router.get("/candidates")
async def list_candidates():
    from app.services.rag_service import get_all_candidates
    return get_all_candidates()


@router.get("/candidate/{candidate_id}/knowledge-map")
async def get_candidate_km(candidate_id: str):
    from app.services.rag_service import get_candidate_knowledge_map
    km = get_candidate_knowledge_map(candidate_id)
    if km is None:
        raise HTTPException(status_code=404, detail="Candidate knowledge map not found")
    return km



@router.post("/answer", response_model=AnswerResponse)
async def answer_interview_question(request: AnswerRequest) -> AnswerResponse:
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="This interview has already been completed")

    unanswered = next((item for item in reversed(session["history"]) if item["answer"] is None), None)
    if unanswered is None:
        raise HTTPException(status_code=409, detail="No unanswered interview question exists")
    unanswered["answer"] = request.answer
    session["question_count"] += 1
    session["answers_answered"] += 1

    covered_topics = covered_topic_names(session["history"])
    can_complete = (
        session["answers_answered"] >= MIN_QUESTIONS
        and len(covered_topics) >= MIN_CURRICULUM_TOPICS
        and session["questions_asked"] >= MAX_QUESTIONS
    )
    if can_complete:
        session["status"] = "completed"
        save_session(session)
        return AnswerResponse(
            session_id=session["session_id"],
            question_number=session["questions_asked"],
            status="completed",
            curriculum_day=unanswered["curriculum_day"],
            curriculum_topic=unanswered["curriculum_topic"],
        )

    cid = session.get("candidate_id")
    target_topic = next_topic(session["history"], candidate_id=cid)
    previous_evaluation = unanswered.get("evaluation")

    # RAG Retrieval & Candidate Intelligence Integration
    from app.services.rag_service import get_candidate_profile, retrieve_context
    cid = session.get("candidate_id")
    rag_chunks = retrieve_context(
        request.answer,
        curriculum_day=target_topic["day"],
        topic=target_topic["name"],
        candidate_id=cid,
        top_k=2,
    )
    cand_profile = get_candidate_profile(cid) if cid else None
    cand_summary = (
        f"Candidate ID: {cid}, Role: {cand_profile.get('member', {}).get('jobRole', 'Engineer')}"
        if cand_profile
        else "General candidate profile"
    )

    next_question = await generate_question(
        unanswered["question"],
        request.answer,
        curriculum_topic=target_topic,
        history=session["history"],
        previous_evaluation=previous_evaluation,
        rag_context=rag_chunks,
        candidate_context=cand_summary,
    )
    session["history"].append(
        {
            "question": next_question,
            "answer": None,
            "curriculum_day": target_topic["day"],
            "curriculum_topic": target_topic["name"],
            "evaluation": None,
        }
    )
    session["questions_asked"] += 1
    save_session(session)
    return AnswerResponse(
        session_id=session["session_id"],
        next_question=next_question,
        question_number=session["questions_asked"],
        status="active",
        curriculum_day=target_topic["day"],
        curriculum_topic=target_topic["name"],
    )


@router.get("/feedback/{session_id}", response_model=FeedbackResponse)
async def get_feedback(session_id: str) -> FeedbackResponse:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found")
    completed_pairs = [item for item in session["history"] if item["answer"] is not None]

    async def get_evaluation(index: int, item: dict) -> EvaluationOutcome:
        cache_key = str(index)
        cached = session["evaluations"].get(cache_key)
        if cached is not None:
            return EvaluationOutcome(result=cached)
        outcome = await evaluate_answer(item["question"], item["answer"])
        # Do not persist a transient failure. A later feedback request retries it.
        if outcome.succeeded:
            session["evaluations"][cache_key] = outcome.result
            item["evaluation"] = outcome.result
        return outcome

    evaluations = await asyncio.gather(
        *(get_evaluation(index, item) for index, item in enumerate(completed_pairs))
    )
    results = []
    for item, outcome in zip(completed_pairs, evaluations, strict=True):
        if outcome.succeeded:
            results.append(
                {
                    "question": item["question"],
                    "answer": item["answer"],
                    "curriculum_day": item["curriculum_day"],
                    "curriculum_topic": item["curriculum_topic"],
                    **outcome.result,
                    "evaluation_status": "succeeded",
                    "evaluation_error": None,
                }
            )
        else:
            results.append(
                {
                    "question": item["question"],
                    "answer": item["answer"],
                    "curriculum_day": item["curriculum_day"],
                    "curriculum_topic": item["curriculum_topic"],
                    "score": None,
                    "strength": None,
                    "weakness": None,
                    "suggestion": None,
                    "evaluation_status": "failed",
                    "evaluation_error": outcome.error,
                }
            )
    save_session(session)
    successful_results = [result for result in results if result["evaluation_status"] == "succeeded"]
    total_score = sum(result["score"] for result in successful_results)
    count = len(successful_results)
    return FeedbackResponse(
        session_id=session["session_id"],
        status=session["status"],
        results=results,
        total_score=total_score,
        average_score=round(total_score / count, 1) if count else 0.0,
        overall_strengths=_deduplicate(result["strength"] for result in successful_results),
        overall_weaknesses=_deduplicate(result["weakness"] for result in successful_results),
        overall_suggestions=_deduplicate(result["suggestion"] for result in successful_results),
        evaluated_count=count,
        covered_curriculum_days=sorted({item["curriculum_day"] for item in completed_pairs}),
        covered_curriculum_topics=sorted(covered_topic_names(completed_pairs)),
    )


def _deduplicate(values: object) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
