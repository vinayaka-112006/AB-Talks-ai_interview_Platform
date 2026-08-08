// lib/api.js
// Integration layer connecting Frontend UI to FastAPI Backend endpoints

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

// ─── Mock Fallbacks ──────────────────────────────────────────────────────────

const MOCK_QUESTIONS = [
  { question: "Tell me about your Python programming experience and relevant technical work.", day: 1, topic: "Python Fundamentals" },
  { question: "How do you design scalable REST APIs using FastAPI and async handlers?", day: 2, topic: "Backend REST APIs" },
  { question: "Explain vector database indexing and embedding retrieval optimization.", day: 3, topic: "Vector Search & Retrieval" },
  { question: "Walk me through how you construct adaptive multi-agent system workflows.", day: 4, topic: "System Architecture & AI Agents" }
];

let mockStep = 0;

async function mockStartInterview() {
  await new Promise((r) => setTimeout(r, 600));
  mockStep = 0;
  return {
    sessionId: `mock-session-${Date.now()}`,
    question: MOCK_QUESTIONS[0].question,
    curriculumDay: MOCK_QUESTIONS[0].day,
    curriculumTopic: MOCK_QUESTIONS[0].topic,
  };
}

async function mockSendAnswer(sessionId, answer) {
  await new Promise((r) => setTimeout(r, 800));
  mockStep++;
  const isCompleted = mockStep >= MOCK_QUESTIONS.length;
  const current = MOCK_QUESTIONS[mockStep] || MOCK_QUESTIONS[MOCK_QUESTIONS.length - 1];

  return {
    sessionId,
    nextQuestion: isCompleted ? null : current.question,
    questionNumber: mockStep + 1,
    status: isCompleted ? 'completed' : 'active',
    curriculumDay: current.day,
    curriculumTopic: current.topic,
  };
}

async function mockGetFeedback(sessionId) {
  await new Promise((r) => setTimeout(r, 700));
  return {
    sessionId,
    status: 'completed',
    totalScore: 84,
    averageScore: 8.4,
    evaluatedCount: 4,
    overallStrengths: [
      "Demonstrates solid understanding of Python async structures.",
      "Clear explanation of REST API design and endpoint validation.",
      "Good awareness of vector search and database retrieval."
    ],
    overallWeaknesses: [
      "Could elaborate more on error handling in streaming endpoints.",
      "Vector indexing tradeoffs could be detailed further."
    ],
    overallSuggestions: [
      "Practice detailed system architecture design diagrams.",
      "Reinforce prompt chaining and guardrail strategies."
    ],
    coveredCurriculumDays: [1, 2, 3, 4],
    coveredCurriculumTopics: [
      "Python Fundamentals",
      "Backend REST APIs",
      "Vector Search & Retrieval",
      "System Architecture & AI Agents"
    ],
    results: MOCK_QUESTIONS.map((q, i) => ({
      question: q.question,
      answer: "Sample detailed technical response provided by the candidate.",
      curriculumDay: q.day,
      curriculumTopic: q.topic,
      score: 8 + (i % 2),
      strength: "Clear technical concepts used.",
      weakness: "Could add more edge-case handling.",
      suggestion: "Reinforce production monitoring patterns.",
      evaluationStatus: "succeeded",
      evaluationError: null,
    }))
  };
}

// ─── Real Backend Integration ────────────────────────────────────────────────

/**
 * Start a new interview session.
 * Endpoint: POST /start-interview
 * @returns {Promise<{ sessionId: string, question: string, curriculumDay: number, curriculumTopic: string }>}
 */
export async function startInterview(candidateId = null) {
  if (MOCK_MODE) return mockStartInterview();

  try {
    const res = await fetch(`${BASE_URL}/start-interview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_id: candidateId }),
    });

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    return {
      sessionId: data.session_id,
      question: data.question,
      curriculumDay: data.curriculum_day,
      curriculumTopic: data.curriculum_topic,
      candidateId: data.candidate_id,
    };
  } catch (err) {
    console.warn("Backend unavailable for startInterview, falling back to mock:", err.message);
    return mockStartInterview();
  }
}

/**
 * Submit candidate's answer to current question.
 * Endpoint: POST /answer
 * @param {string} sessionId
 * @param {string} answer
 * @returns {Promise<{ sessionId: string, nextQuestion: string|null, questionNumber: number, status: 'active'|'completed', curriculumDay: number, curriculumTopic: string }>}
 */
export async function sendAnswer(sessionId, answer) {
  if (MOCK_MODE || sessionId.startsWith('mock-')) {
    return mockSendAnswer(sessionId, answer);
  }

  try {
    const res = await fetch(`${BASE_URL}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        answer: answer,
      }),
    });

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    return {
      sessionId: data.session_id,
      nextQuestion: data.next_question || null,
      questionNumber: data.question_number,
      status: data.status,
      curriculumDay: data.curriculum_day || 1,
      curriculumTopic: data.curriculum_topic || "Assessment",
    };
  } catch (err) {
    console.warn("Backend unavailable for sendAnswer, falling back to mock:", err.message);
    return mockSendAnswer(sessionId, answer);
  }
}

/**
 * Get final assessment report feedback for session.
 * Endpoint: GET /feedback/{session_id}
 * @param {string} sessionId
 * @returns {Promise<object>}
 */
export async function getFeedback(sessionId) {
  if (MOCK_MODE || !sessionId || sessionId.startsWith('mock-')) {
    return mockGetFeedback(sessionId);
  }

  try {
    const res = await fetch(`${BASE_URL}/feedback/${encodeURIComponent(sessionId)}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();

    return {
      sessionId: data.session_id,
      status: data.status,
      totalScore: data.total_score || 0,
      averageScore: data.average_score || 0,
      evaluatedCount: data.evaluated_count || 0,
      overallStrengths: data.overall_strengths || [],
      overallWeaknesses: data.overall_weaknesses || [],
      overallSuggestions: data.overall_suggestions || [],
      coveredCurriculumDays: data.covered_curriculum_days || [],
      coveredCurriculumTopics: data.covered_curriculum_topics || [],
      results: (data.results || []).map((r) => ({
        question: r.question,
        answer: r.answer,
        curriculumDay: r.curriculum_day,
        curriculumTopic: r.curriculum_topic,
        score: r.score,
        strength: r.strength,
        weakness: r.weakness,
        suggestion: r.suggestion,
        evaluationStatus: r.evaluation_status,
        evaluationError: r.evaluation_error,
      })),
    };
  } catch (err) {
    console.warn("Backend unavailable for getFeedback, falling back to mock:", err.message);
    return mockGetFeedback(sessionId);
  }
}

/**
 * Fetch the real knowledge map for a candidate.
 * Endpoint: GET /candidate/{candidate_id}/knowledge-map
 * @param {string} candidateId
 * @returns {Promise<object>}
 */
export async function getCandidateKnowledgeMap(candidateId) {
  if (MOCK_MODE || !candidateId) return null;

  try {
    const res = await fetch(`${BASE_URL}/candidate/${encodeURIComponent(candidateId)}/knowledge-map`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    return await res.json();
  } catch (err) {
    console.warn("Backend unavailable for getCandidateKnowledgeMap:", err.message);
    return null;
  }
}


