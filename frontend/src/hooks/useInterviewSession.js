// src/hooks/useInterviewSession.js
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import { startInterview, sendAnswer } from '../lib/api';
import { MOCK_INTERVIEW_QUESTIONS } from '../lib/interviewQuestionsData';
import { MOCK_CANDIDATES } from '../lib/candidatesData';
import { MOCK_KNOWLEDGE_MAP } from '../lib/mockKnowledgeMap';

export const SESSION_STATES = {
  QUESTION: 'QUESTION',
  SUBMITTING: 'SUBMITTING',
  ANALYZING: 'ANALYZING',
  SHOWING_FOLLOW_UP: 'SHOWING_FOLLOW_UP',
  COMPLETED: 'COMPLETED',
};

const TOPIC_CONCEPT_MAP = {
  "Python Fundamentals": "embeddings",
  "Backend REST APIs": "rag_retrieval",
  "Databases": "vector_db",
  "Security": "rag_gen",
  "Production Observability": "observability",
};

export function useInterviewSession() {
  const router = useRouter();
  const [candidate, setCandidate] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState(MOCK_INTERVIEW_QUESTIONS[0]);
  const [sessionState, setSessionState] = useState(SESSION_STATES.QUESTION);
  const [answerHistory, setAnswerHistory] = useState([]);
  const [exploredConceptIds, setExploredConceptIds] = useState(['embeddings']);
  const [activeConceptId, setActiveConceptId] = useState('embeddings');
  const isInitialized = useRef(false);

  // Load candidate and start backend interview session on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && !isInitialized.current) {
      isInitialized.current = true;
      const stored = sessionStorage.getItem('selected_candidate');
      if (stored) {
        try { setCandidate(JSON.parse(stored)); } catch (e) { setCandidate(MOCK_CANDIDATES[0]); }
      } else {
        setCandidate(MOCK_CANDIDATES[0]);
      }

      // Call backend start-interview with selected candidate's ID
      const candidateId = stored ? JSON.parse(stored)?.id : MOCK_CANDIDATES[0]?.id;
      startInterview(candidateId).then((res) => {
        if (res?.sessionId) {
          setSessionId(res.sessionId);
          sessionStorage.setItem('current_session_id', res.sessionId);
          if (res.question) {
            const mappedConcept = TOPIC_CONCEPT_MAP[res.curriculumTopic] || 'embeddings';
            setCurrentQuestion({
              id: `q-1`,
              topic: res.curriculumTopic || "Python Fundamentals",
              question: res.question,
              difficulty: "CORE",
              conceptId: mappedConcept,
            });
            setActiveConceptId(mappedConcept);
            setExploredConceptIds([mappedConcept]);
          }
        }
      });
    }
  }, []);

  const submitAnswer = async (answerText) => {
    if (!answerText.trim() || sessionState !== SESSION_STATES.QUESTION) return;

    // 1. Enter SUBMITTING state
    setSessionState(SESSION_STATES.SUBMITTING);

    const newEntry = {
      questionId: currentQuestion.id,
      questionTopic: currentQuestion.topic,
      conceptId: currentQuestion.conceptId,
      isFollowUp: false,
      answer: answerText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const updatedHistory = [...answerHistory, newEntry];
    setAnswerHistory(updatedHistory);

    // 2. Transition to ANALYZING state
    setSessionState(SESSION_STATES.ANALYZING);

    // Send answer to backend
    const activeSessionId = sessionId || (typeof window !== 'undefined' ? sessionStorage.getItem('current_session_id') : null) || 'default-session';
    const apiRes = await sendAnswer(activeSessionId, answerText);

    setTimeout(() => {
      if (apiRes.status === 'completed' || !apiRes.nextQuestion) {
        setSessionState(SESSION_STATES.COMPLETED);
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('assessment_history', JSON.stringify(updatedHistory));
        }
        router.push('/feedback');
      } else {
        const nextIndex = currentQuestionIndex + 1;
        setCurrentQuestionIndex(nextIndex);
        const mappedConcept = TOPIC_CONCEPT_MAP[apiRes.curriculumTopic] || `concept_${nextIndex}`;
        
        setCurrentQuestion({
          id: `q-${nextIndex + 1}`,
          topic: apiRes.curriculumTopic || `Topic ${nextIndex + 1}`,
          question: apiRes.nextQuestion,
          difficulty: nextIndex > 1 ? "ADVANCED" : "CORE",
          conceptId: mappedConcept,
        });

        setActiveConceptId(mappedConcept);
        setExploredConceptIds((prev) => prev.includes(mappedConcept) ? prev : [...prev, mappedConcept]);
        setSessionState(SESSION_STATES.QUESTION);
      }
    }, 1200);
  };

  return {
    candidate,
    sessionId,
    questions: MOCK_INTERVIEW_QUESTIONS,
    currentQuestion,
    currentQuestionIndex,
    currentStep: currentQuestionIndex + 1,
    totalSteps: Math.max(4, currentQuestionIndex + 1),
    sessionState,
    isAnalyzing: sessionState === SESSION_STATES.ANALYZING || sessionState === SESSION_STATES.SUBMITTING,
    isFollowUpNext: false,
    answerHistory,
    knowledgeMap: MOCK_KNOWLEDGE_MAP,
    activeConceptId,
    exploredConceptIds,
    submitAnswer,
  };
}

