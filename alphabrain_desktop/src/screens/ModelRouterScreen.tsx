import React, { useState, useEffect } from 'react';
import { desktopApi } from '../api/client';
import { ModelUtilityScore } from '../types';
import { RefreshCw, Zap } from 'lucide-react';

export const ModelRouterScreen: React.FC = () => {
  const [scores, setScores] = useState<ModelUtilityScore[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchScores = () => {
    setLoading(true);
    desktopApi
      .getModelScores()
      .then((data) => {
        setScores(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load model scores:', err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchScores();
  }, []);

  const activeAccount = scores.find((s) => s.account_name.includes('[ACTIVE]')) || scores[0];

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-6">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#E6391E] font-bold uppercase tracking-widest">
              TELEMETRY // MULTI-ACCOUNT OC-EDS SCHEDULER
            </span>
            <span className="text-neutral-300">•</span>
            <span className="font-mono text-xs text-neutral-500 uppercase">
              SMOOTH UTILITY ROUTING
            </span>
          </div>
          <h1 className="text-3xl font-bold font-sans tracking-tight mt-1 text-[#0A0A0A]">
            AI Quotas & Model Router
          </h1>
          <p className="font-mono text-xs text-neutral-500 mt-1">
            Live Google Cloud Code telemetry and autonomous utility scoring across registered accounts
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchScores}
            className="flex items-center gap-2 px-4 py-2 border border-[#0A0A0A] bg-white font-mono text-xs font-bold hover:bg-neutral-100 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#E6391E]' : ''}`} />
            <span>REFRESH TELEMETRY</span>
          </button>
        </div>
      </div>

      {/* Active Account Hero Spotlight */}
      {activeAccount && (
        <div className="border-2 border-[#0A0A0A] bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between border-b border-neutral-200 pb-3">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#E6391E]" />
              <span className="font-mono text-xs font-bold uppercase tracking-widest text-[#0A0A0A]">
                ACTIVE ROUTING PROFILE
              </span>
              <span className="font-mono text-[10px] bg-[#E6391E] text-white font-bold px-2 py-0.5 uppercase">
                DISPATCH TARGET
              </span>
            </div>
            <span className="font-mono text-xs text-neutral-500">
              TIER: <strong className="text-black uppercase">{activeAccount.tier}</strong>
            </span>
          </div>

          <div className="mt-4 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <h2 className="text-2xl font-bold font-sans text-[#0A0A0A]">
                {activeAccount.email}
              </h2>
              <div className="font-mono text-xs text-neutral-500 mt-1 flex items-center gap-3">
                <span>PROFILE: <strong className="text-black">{activeAccount.account_name}</strong></span>
                <span>•</span>
                <span>RECOMMENDED MODEL: <strong className="text-[#E6391E]">{activeAccount.recommended_model}</strong></span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 border border-[#0A0A0A] bg-neutral-50 p-4 font-mono">
              <div className="text-center px-4">
                <span className="text-[10px] text-neutral-500 uppercase block">Weekly Quota</span>
                <span className="text-2xl font-bold text-[#E6391E]">
                  {activeAccount.weekly_quota_percent}%
                </span>
              </div>
              <div className="text-center px-4 border-l border-neutral-300">
                <span className="text-[10px] text-neutral-500 uppercase block">5-Hour Quota</span>
                <span className="text-2xl font-bold text-[#0A0A0A]">
                  {activeAccount.five_hour_quota_percent}%
                </span>
              </div>
              <div className="text-center px-4 border-l border-neutral-300">
                <span className="text-[10px] text-neutral-500 uppercase block">Utility Score</span>
                <span className="text-2xl font-bold text-emerald-700">
                  {activeAccount.utility_score > 0 ? activeAccount.utility_score.toFixed(2) : '0.00'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Account Pool Roster Table */}
      <div className="border border-[#0A0A0A] bg-white">
        <div className="grid grid-cols-12 px-6 py-3 border-b border-[#0A0A0A] bg-neutral-50 font-mono text-xs text-neutral-500 font-bold uppercase">
          <div className="col-span-1">Rank</div>
          <div className="col-span-4">Account / Email</div>
          <div className="col-span-2">Priority Tier</div>
          <div className="col-span-2">Recommended Model</div>
          <div className="col-span-1 text-center">Weekly</div>
          <div className="col-span-2 text-right">Utility Score (U)</div>
        </div>

        {loading ? (
          <div className="p-12 text-center font-mono text-xs text-neutral-400">
            Querying Google Cloud Code quota summaries...
          </div>
        ) : scores.length === 0 ? (
          <div className="p-12 text-center font-mono text-xs text-neutral-400">
            No accounts registered in pool.
          </div>
        ) : (
          <div className="divide-y divide-neutral-200">
            {scores.map((s, idx) => {
              const isActive = s.account_name.includes('[ACTIVE]');
              const isExhausted = s.tier.toLowerCase().includes('disqualified') || s.tier.toLowerCase().includes('exhausted');

              return (
                <div
                  key={s.email}
                  className={`grid grid-cols-12 px-6 py-4 items-center transition-colors ${
                    isActive ? 'bg-neutral-50' : 'hover:bg-neutral-50'
                  }`}
                >
                  <div className="col-span-1 font-mono text-xs font-bold text-neutral-400">
                    {String(idx + 1).padStart(2, '0')}
                  </div>

                  <div className="col-span-4 flex items-center gap-2">
                    <span className="font-bold text-sm text-[#0A0A0A]">{s.email}</span>
                    {isActive && (
                      <span className="font-mono text-[9px] bg-[#E6391E] text-white font-bold px-1.5 py-0.5 uppercase">
                        ACTIVE
                      </span>
                    )}
                  </div>

                  <div className="col-span-2 font-mono text-xs text-neutral-600">
                    {s.tier}
                  </div>

                  <div className="col-span-2 font-mono text-xs font-bold text-[#0A0A0A]">
                    {s.recommended_model}
                  </div>

                  <div className="col-span-1 text-center font-mono text-sm font-bold">
                    <span className={isExhausted ? 'text-neutral-400 line-through' : 'text-[#E6391E]'}>
                      {s.weekly_quota_percent}%
                    </span>
                  </div>

                  <div className="col-span-2 text-right font-mono text-sm font-bold text-[#0A0A0A]">
                    {s.utility_score > 0 ? s.utility_score.toFixed(2) : '-inf'}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer statistics summary */}
      <div className="border border-[#0A0A0A] bg-neutral-50 p-4 font-mono text-xs flex justify-between items-center">
        <span className="text-neutral-500">SCHEDULER ACCOUNT POOL</span>
        <span className="font-bold text-[#0A0A0A]">
          {scores.length} REGISTERED AI PRO ACCOUNTS
        </span>
      </div>
    </div>
  );
};
