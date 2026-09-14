import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';
import { ModelUtilityScore } from '../types';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SkeletonCard, SkeletonList } from '../components/ui/Skeleton';

export const ModelRouterScreen: React.FC = () => {
  const [scores, setScores] = useState<ModelUtilityScore[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi
      .getModelScores()
      .then((data) => {
        setScores(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const activeAccount = scores.find((s) => s.account_name.includes('[ACTIVE]')) || scores[0];

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh] animate-screen-enter">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          TELEMETRY // MULTI-ACCOUNT OC-EDS SCHEDULER
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          AI Quotas
        </h2>
      </div>

      {/* Active Account Overview Hero */}
      {loading ? (
        <SkeletonCard />
      ) : activeAccount ? (
        <div className="border border-[#0A0A0A] p-4 my-3 bg-zinc-50 hover-lift transition-smooth">
          <div className="flex items-center justify-between font-mono text-[10px] text-zinc-500 uppercase">
            <span>ACTIVE PROFILE</span>
            <span className="text-[#E6391E] font-bold">LIVE TELEMETRY</span>
          </div>
          <div className="text-lg font-headline font-bold mt-1 text-[#0A0A0A] truncate">
            {activeAccount.email}
          </div>
          <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-zinc-200 font-mono">
            <div>
              <span className="text-[10px] text-zinc-500 uppercase block">Gemini Weekly</span>
              <span className="text-2xl font-bold text-[#E6391E]">
                {activeAccount.weekly_quota_percent}%
              </span>
            </div>
            <div>
              <span className="text-[10px] text-zinc-500 uppercase block">Utility Score</span>
              <span className="text-2xl font-bold text-[#0A0A0A]">
                {activeAccount.utility_score > 0 ? activeAccount.utility_score.toFixed(2) : '0.00'}
              </span>
            </div>
          </div>
        </div>
      ) : null}

      {/* 8 Real Accounts List */}
      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-2 overflow-y-auto max-h-[45vh]">
        {loading ? (
          <div className="space-y-4">
            <div className="p-4 flex items-center justify-center bg-zinc-50 border border-zinc-200">
              <LoadingSpinner size="md" label="Querying Google Cloud Code quota summaries..." />
            </div>
            <SkeletonList rows={4} />
          </div>
        ) : (
          scores.map((s, idx) => {
            const isActive = s.account_name.includes('[ACTIVE]');
            const isExhausted = s.tier.toLowerCase().includes('disqualified') || s.tier.toLowerCase().includes('exhausted');

            return (
              <div
                key={s.email}
                className={`py-3 px-2 flex items-center justify-between card-tactile hover-lift transition-smooth ${
                  isActive ? 'bg-zinc-100' : 'hover:bg-zinc-50'
                }`}
              >
                <div className="flex-1 min-w-0 pr-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-zinc-400">0{idx + 1}</span>
                    <span className="font-bold text-xs truncate text-[#0A0A0A]">
                      {s.email.split('@')[0]}
                    </span>
                    {isActive && (
                      <span className="font-mono text-[9px] bg-[#E6391E] text-white font-bold px-1.5 py-0.2">
                        ACTIVE
                      </span>
                    )}
                  </div>
                  <div className="font-mono text-[10px] text-zinc-500 mt-1 flex gap-2">
                    <span>{s.tier}</span>
                    <span>•</span>
                    <span className="text-[#0A0A0A] font-semibold">{s.recommended_model.split('-')[0]}</span>
                  </div>
                </div>

                <div className="text-right font-mono">
                  <span
                    className={`text-sm font-bold block ${
                      isExhausted ? 'text-zinc-400 line-through' : 'text-[#E6391E]'
                    }`}
                  >
                    {s.weekly_quota_percent}%
                  </span>
                  <span className="text-[9px] text-zinc-400 uppercase">
                    U: {s.utility_score > 0 ? s.utility_score.toFixed(1) : '-inf'}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex items-center justify-between font-mono text-xs">
        <span className="text-zinc-500">ACCOUNT POOL</span>
        <span className="font-bold text-[#0A0A0A]">{scores.length} REGISTERED</span>
      </div>
    </div>
  );
};
