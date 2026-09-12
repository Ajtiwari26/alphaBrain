import React, { useState, useEffect } from 'react';
import { ModelUtilityScore } from '../types';
import { mobileApi } from '../api/client';
import { Cpu, Award, Zap, CheckCircle2, TrendingUp } from 'lucide-react';

export const ModelRouterScreen: React.FC = () => {
  const [scores, setScores] = useState<ModelUtilityScore[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi.getModelScores().then((data) => {
      setScores(data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Computing OC-EDS Utility Scores...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">12 // MODEL ROUTER</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">OC-EDS Utility</h1>
        </div>
        <span className="font-mono text-xs px-2.5 py-1 rounded bg-accent/10 text-accent border border-accent/40 font-semibold">
          OPUS 4.6 PRIORITY
        </span>
      </div>

      {/* Formula Explanation Card */}
      <div className="locomotive-card p-3.5 rounded-lg text-xs font-mono space-y-1">
        <div className="text-muted text-[10px] uppercase">TIERED OPPORTUNITY-COST / EARLIEST-DEADLINE SCHEDULING</div>
        <div className="text-accent font-semibold">Tier 1: U = 1000.0 + F_i (Idle First to break 7-day seal)</div>
        <div className="text-slate-400 text-[11px]">Rotates across multi-account pool to maximize Claude Opus capacity.</div>
      </div>

      {/* Accounts List */}
      <div className="space-y-3">
        {scores.map((sc, idx) => (
          <div key={sc.email} className={`locomotive-card p-4 rounded-lg space-y-3 ${
            idx === 0 ? 'border-accent shadow-md shadow-accent/10' : ''
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-accent font-bold">0{idx + 1}</span>
                  <span className="font-display text-sm font-semibold text-white">{sc.account_name}</span>
                </div>
                <div className="font-mono text-xs text-muted mt-0.5">{sc.email}</div>
              </div>
              <div className="text-right">
                <span className="font-mono text-xs text-accent font-bold block">{sc.utility_score.toFixed(1)}</span>
                <span className="font-mono text-[10px] text-muted uppercase">Utility U</span>
              </div>
            </div>

            <div className="p-2.5 rounded bg-background border border-card-border font-mono text-xs space-y-1 text-slate-300">
              <div className="flex justify-between">
                <span className="text-muted">Scheduling Tier:</span>
                <span className="text-emerald-400 font-semibold">{sc.tier}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Weekly Quota Remaining:</span>
                <span>{sc.weekly_quota_percent}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">5-Hour Quota Remaining:</span>
                <span>{sc.five_hour_quota_percent}%</span>
              </div>
              <div className="flex justify-between pt-1 border-t border-card-border">
                <span className="text-muted">Target Model:</span>
                <span className="text-accent font-semibold">{sc.recommended_model}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
