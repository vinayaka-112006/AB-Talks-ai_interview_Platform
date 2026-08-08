import React, { useState, useEffect } from 'react';
import FeedbackReport from '../components/FeedbackReport';
import { getFeedback } from '../lib/api';
import { MOCK_FEEDBACK_DATA } from '../lib/mockFeedback';

export default function FeedbackPage({ appTheme, onToggleTheme }) {
  const [candidate, setCandidate] = useState(null);
  const [feedbackData, setFeedbackData] = useState(MOCK_FEEDBACK_DATA);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const storedCandidate = sessionStorage.getItem('selected_candidate');
      const activeSessionId = sessionStorage.getItem('current_session_id');

      if (storedCandidate) {
        try { setCandidate(JSON.parse(storedCandidate)); } catch (e) {}
      }

      if (activeSessionId) {
        getFeedback(activeSessionId).then((res) => {
          if (res) {
            setFeedbackData({
              ...MOCK_FEEDBACK_DATA,
              overallScore: {
                ...MOCK_FEEDBACK_DATA.overallScore,
                score: res.totalScore || res.averageScore * 10 || 84,
              },
              strengths: res.overallStrengths?.length ? res.overallStrengths : MOCK_FEEDBACK_DATA.strengths,
              knowledgeGaps: res.overallWeaknesses?.length ? res.overallWeaknesses : MOCK_FEEDBACK_DATA.knowledgeGaps,
              recommendations: res.overallSuggestions?.length ? res.overallSuggestions : MOCK_FEEDBACK_DATA.recommendations,
            });
          }
        });
      }
    }
  }, []);

  return (
    <FeedbackReport
      feedbackData={feedbackData}
      candidate={candidate}
      appTheme={appTheme}
      onToggleTheme={onToggleTheme}
    />
  );
}


