import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';
import { ModelUtilityScore } from '../types';

export const ModelRouterScreen: React.FC = () => {
  const [scores, setScores] = useState<ModelUtilityScore[]>([]);

  useEffect(() => {
    mobileApi.getModelScores().then(setScores).catch(console.error);
  }, []);

  const geminiScore = scores.find((s) => s.email.includes('aj') || s.recommended_model.includes('gemini'));
  const opusScore = scores.find((s) => s.recommended_model.includes('opus'));

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          TELEMETRY // OC-EDS
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          AI Quotas
        </h2>
      </div>

      <div className="flex-1 flex flex-col justify-center divide-y divide-[#0A0A0A] my-4">
        <div className="py-6">
          <span className="font-mono text-xs text-zinc-500 uppercase tracking-wider">
            GEMINI PRO HIGH
          </span>
          <div className="text-7xl font-headline font-bold text-[#E6391E] mt-1 leading-none">
            {geminiScore ? `${Math.round(geminiScore.weekly_quota_percent)}%` : '85%'}
          </div>
          <span className="font-mono text-[10px] text-zinc-400 mt-2 block uppercase">
            ACCOUNT 01 // 6H TIER • UTILITY: {geminiScore ? geminiScore.utility_score.toFixed(1) : '1042.0'}
          </span>
        </div>

        <div className="py-6">
          <span className="font-mono text-xs text-zinc-500 uppercase tracking-wider">
            CLAUDE OPUS
          </span>
          <div className="text-7xl font-headline font-bold text-[#0A0A0A] mt-1 leading-none">
            {opusScore ? `${Math.round(opusScore.weekly_quota_percent)}%` : '42%'}
          </div>
          <span className="font-mono text-[10px] text-zinc-400 mt-2 block uppercase">
            ARCHITECTURAL SEAT // SENIOR REVIEW INVARIANT
          </span>
        </div>
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex items-center justify-between">
        <span className="font-mono text-[11px] text-zinc-500 uppercase">
          NEXT REFRESH CYCLE:
        </span>
        <span className="font-mono text-[11px] font-bold text-[#E6391E]">
          04H 20M
        </span>
      </div>
    </div>
  );
};
