from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.utils.sanitizer import MAX_ANSWER_LENGTH, sanitize_prompt_input


class AnswerRequest(BaseModel):
    session_id: str
    answer: str = Field(..., min_length=1, max_length=MAX_ANSWER_LENGTH)

    @field_validator("answer")
    @classmethod
    def sanitize_answer(cls, value: str) -> str:
        value = sanitize_prompt_input(value)
        if not value:
            raise ValueError("answer must contain visible characters")
        return value


class StartInterviewRequest(BaseModel):
    candidate_id: str | None = None


class StartInterviewResponse(BaseModel):
    session_id: str
    question: str
    curriculum_day: int
    curriculum_topic: str
    candidate_id: str | None = None


class AnswerResponse(BaseModel):
    session_id: str
    next_question: str | None = None
    question_number: int
    status: Literal["active", "completed"]
    curriculum_day: int | None = None
    curriculum_topic: str | None = None


class EvaluationResult(BaseModel):
    question: str
    answer: str
    curriculum_day: int
    curriculum_topic: str
    score: int | None = Field(default=None, ge=0, le=10)
    strength: str | None = None
    weakness: str | None = None
    suggestion: str | None = None
    evaluation_status: Literal["succeeded", "failed"]
    evaluation_error: str | None = None


class FeedbackResponse(BaseModel):
    session_id: str
    status: Literal["active", "completed"]
    results: list[EvaluationResult]
    total_score: int
    average_score: float
    overall_strengths: list[str]
    overall_weaknesses: list[str]
    overall_suggestions: list[str]
    evaluated_count: int
    covered_curriculum_days: list[int]
    covered_curriculum_topics: list[str]
