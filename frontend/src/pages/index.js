// src/pages/index.js
import { useState, useEffect } from 'react';
import CandidateSelector from '../components/CandidateSelector';
import { MOCK_CANDIDATES } from '../lib/candidatesData';

export default function IndexPage({ appTheme, onToggleTheme }) {
  const [candidates, setCandidates] = useState(MOCK_CANDIDATES);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/candidates`)
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const formatted = data.map((c) => ({
            member: {
              id: c.id,
              name: c.name,
              jobRole: c.jobRole,
              yearsExperience: c.yearsExperience,
              education: c.education,
              status: c.status || 'COMPLETED',
            },
            missions: [],
            signals: {
              commitDays: c.commitDays || 25,
              missionsCompleted: c.missionsCompleted || 28,
              missionsFirstTry: 18,
            },
          }));
          setCandidates(formatted);
        }
      })
      .catch(() => {});
  }, []);

  return <CandidateSelector candidates={candidates} appTheme={appTheme} onToggleTheme={onToggleTheme} />;
}


