import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';
import { ModelUtilityScore } from '../types';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SkeletonCard, SkeletonList } from '../components/ui/Skeleton';
import { 
  Sparkles, 
  Zap, 
  RefreshCw, 
  ArrowLeft, 
  ArrowRight, 
  ShieldCheck, 
  Clock, 
  CheckCircle2, 
  Cpu
} from 'lucide-react';

export const ModelRouterScreen: React.FC = () => {
  const [scores, setScores] = useState<ModelUtilityScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<ModelUtilityScore | null>(null);

  const fetchScores = () => {
    mobileApi
      .getModelScores()
      .then((data) => {
        setScores(data);
        setLoading(false);
        setRefreshing(false);
        // If an account is currently selected, refresh its reference
        if (selectedAccount) {
          const updated = data.find((d) => d.email === selectedAccount.email);
          if (updated) setSelectedAccount(updated);
        }
      })
      .catch((err) => {
        console.error('Failed to load model scores:', err);
        setLoading(false);
        setRefreshing(false);
      });
  };

  useEffect(() => {
    fetchScores();
  }, []);

  const handleManualRefresh = () => {
    setRefreshing(true);
    fetchScores();
  };

  const activeAccount = scores.find((s) => s.is_active || s.account_name.includes('[ACTIVE]')) || scores[0];

  const cleanResetDesc = (desc?: string): string => {
    if (!desc) return '';
    if (desc.toLowerCase().includes('refresh in')) {
      const parts = desc.split(/refresh in/i);
      if (parts.length > 1) {
        return 'Refreshes in ' + parts[1].replace(/\.$/, '').trim();
      }
    }
    if (desc.toLowerCase().includes('refreshes in')) {
      const parts = desc.split(/refreshes in/i);
      if (parts.length > 1) {
        return 'Refreshes in ' + parts[1].split('.')[0].trim();
      }
    }
    return desc.length > 60 ? desc.slice(0, 57) + '...' : desc;
  };

  // ─────────────────────────────────────────────────────────────
  // VIEW 2: DEDICATED FULL DETAIL SCREEN (ON REDIRECT)
  // ─────────────────────────────────────────────────────────────
  if (selectedAccount) {
    const acc = selectedAccount;
    const isActive = acc.is_active || acc.account_name.includes('[ACTIVE]');
    const gemini5h = acc.gemini_5h_percent ?? acc.five_hour_quota_percent ?? 100;
    const geminiWk = acc.gemini_weekly_percent ?? acc.weekly_quota_percent ?? 0;
    const claude5h = acc.claude_5h_percent ?? 100;
    const claudeWk = acc.claude_weekly_percent ?? 0;

    return (
      <div className="flex-1 flex flex-col bg-white text-[#0A0A0A] animate-screen-enter space-y-4 pb-[max(env(safe-area-inset-bottom),5rem)]">
        {/* Detail Top Bar */}
        <div className="border-b border-[#0A0A0A] pb-3 flex items-center justify-between">
          <button
            onClick={() => setSelectedAccount(null)}
            className="flex items-center gap-1.5 font-mono text-xs font-bold text-[#0A0A0A] hover:text-[#E6391E] transition-colors py-1"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Quotas List</span>
          </button>
          <span className="font-mono text-[9px] px-2 py-0.5 border border-[#0A0A0A] font-bold">
            ACCOUNT DETAIL
          </span>
        </div>

        {/* Account Identity Header */}
        <div className="border border-[#0A0A0A] p-4 bg-zinc-50 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-xs font-bold text-zinc-400">
                {scores.findIndex((s) => s.email === acc.email) + 1}
              </span>
              <span className="font-headline text-base font-bold text-[#0A0A0A] truncate max-w-[220px]">
                {acc.email}
              </span>
            </div>
            {isActive ? (
              <span className="font-mono text-[9px] px-2 py-0.5 bg-[#E6391E] text-white font-bold uppercase">
                ACTIVE PRODUCTION
              </span>
            ) : (
              <span className="font-mono text-[9px] px-2 py-0.5 border border-zinc-300 text-zinc-600 font-bold uppercase">
                STANDBY POOL
              </span>
            )}
          </div>

          <div className="flex items-center justify-between font-mono text-xs pt-2 border-t border-zinc-200">
            <span className="text-zinc-600">
              Tier: <strong className="text-[#0A0A0A]">{acc.tier}</strong>
            </span>
            <span className="text-zinc-600">
              Utility Score: <strong className="text-[#E6391E]">{acc.utility_score > 0 ? acc.utility_score.toFixed(2) : '-inf'}</strong>
            </span>
          </div>
          <div className="font-mono text-[10px] text-zinc-500">
            Recommended: <strong className="text-[#0A0A0A]">{acc.recommended_model}</strong>
          </div>
        </div>

        {/* Section 1: Gemini 3.1 Pro Limits */}
        <div className="border border-[#0A0A0A] p-4 bg-white space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-200 pb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#E6391E]" />
              <span className="font-headline text-sm font-bold uppercase tracking-tight">Gemini 3.1 Pro Limits</span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500 uppercase">Google AI Pro</span>
          </div>

          <div className="space-y-1 font-mono text-xs">
            <div className="flex justify-between">
              <span className="text-zinc-600">5-Hour Rolling Limit:</span>
              <span className="font-bold text-[#0A0A0A]">{gemini5h}%</span>
            </div>
            <div className="w-full h-2 bg-zinc-100 border border-[#0A0A0A] overflow-hidden p-[1px]">
              <div className="h-full bg-[#0A0A0A]" style={{ width: `${Math.min(100, Math.max(4, gemini5h))}%` }} />
            </div>
            {acc.gemini_5h_desc && (
              <p className="text-[9px] text-zinc-500 pt-0.5">{cleanResetDesc(acc.gemini_5h_desc)}</p>
            )}
          </div>

          <div className="space-y-1 font-mono text-xs pt-1">
            <div className="flex justify-between">
              <span className="text-zinc-600">Weekly Limit:</span>
              <span className="font-bold text-[#E6391E]">{geminiWk}%</span>
            </div>
            <div className="w-full h-2 bg-zinc-100 border border-[#0A0A0A] overflow-hidden p-[1px]">
              <div className="h-full bg-[#E6391E]" style={{ width: `${Math.min(100, Math.max(4, geminiWk))}%` }} />
            </div>
            {acc.gemini_weekly_desc && (
              <p className="text-[9px] text-zinc-500 pt-0.5">{cleanResetDesc(acc.gemini_weekly_desc)}</p>
            )}
          </div>
        </div>

        {/* Section 2: Claude Opus / 3.7 Limits */}
        <div className="border border-[#0A0A0A] p-4 bg-white space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-200 pb-2">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#0A0A0A]" />
              <span className="font-headline text-sm font-bold uppercase tracking-tight">Claude Opus 4.6 / 3.7 Limits</span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500 uppercase">Anthropic Model</span>
          </div>

          <div className="space-y-1 font-mono text-xs">
            <div className="flex justify-between">
              <span className="text-zinc-600">5-Hour Rolling Limit:</span>
              <span className="font-bold text-[#0A0A0A]">{claude5h}%</span>
            </div>
            <div className="w-full h-2 bg-zinc-100 border border-[#0A0A0A] overflow-hidden p-[1px]">
              <div className="h-full bg-[#0A0A0A]" style={{ width: `${Math.min(100, Math.max(4, claude5h))}%` }} />
            </div>
            {acc.claude_5h_desc && (
              <p className="text-[9px] text-zinc-500 pt-0.5">{cleanResetDesc(acc.claude_5h_desc)}</p>
            )}
          </div>

          <div className="space-y-1 font-mono text-xs pt-1">
            <div className="flex justify-between">
              <span className="text-zinc-600">Weekly Limit:</span>
              <span className={`font-bold ${claudeWk > 0 ? 'text-[#E6391E]' : 'text-zinc-400 line-through'}`}>{claudeWk}%</span>
            </div>
            <div className="w-full h-2 bg-zinc-100 border border-[#0A0A0A] overflow-hidden p-[1px]">
              <div className="h-full bg-[#E6391E]" style={{ width: `${Math.min(100, Math.max(4, claudeWk))}%` }} />
            </div>
            {acc.claude_weekly_desc && (
              <p className="text-[9px] text-zinc-500 pt-0.5">{cleanResetDesc(acc.claude_weekly_desc)}</p>
            )}
          </div>
        </div>

        {/* Section 3: Token Health & Rotation Status */}
        <div className="border border-zinc-300 p-3 bg-zinc-50 font-mono text-[10px] text-zinc-600 space-y-1.5">
          <div className="flex items-center justify-between font-bold text-[#0A0A0A]">
            <span className="flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              Token Status: 🟢 Valid & Synced
            </span>
            <span>Local Profile: ~/.gemini/profiles/{acc.email.split('@')[0]}</span>
          </div>
          <p className="text-[9px] text-zinc-500">
            Managed autonomously by agy-switch. To switch to this account manually on host Mac: <code className="text-[#0A0A0A] font-bold">agy-switch {acc.email.split('@')[0]}</code>
          </p>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // VIEW 1: ONE-LINE QUOTAS LIST (MAIN SCREEN)
  // ─────────────────────────────────────────────────────────────
  return (
    <div className="flex-1 flex flex-col bg-white text-[#0A0A0A] animate-screen-enter space-y-4 pb-[max(env(safe-area-inset-bottom),5rem)]">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-3 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
              OC-EDS MODEL SCHEDULER
            </span>
            <span className="font-mono text-[9px] px-1.5 py-0.2 bg-[#0A0A0A] text-white font-bold uppercase">
              {scores.length} ACCOUNTS
            </span>
          </div>
          <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
            AI Model Quotas
          </h2>
          <p className="font-mono text-[11px] text-zinc-500 mt-0.5">
            Real-time Gemini & Claude 5h & weekly limits across 8 accounts
          </p>
        </div>
        <button
          onClick={handleManualRefresh}
          disabled={refreshing}
          className="p-2 border border-[#0A0A0A] hover:bg-zinc-100 transition-colors shrink-0 mt-1"
          title="Refresh live telemetry"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-[#0A0A0A] ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Active Account Quick Banner */}
      {activeAccount && (
        <div 
          onClick={() => setSelectedAccount(activeAccount)}
          className="border-2 border-[#0A0A0A] p-3 bg-zinc-50 flex items-center justify-between cursor-pointer hover:bg-zinc-100 transition-colors group"
        >
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-pulse" />
              <span className="font-mono text-[9px] text-zinc-500 uppercase font-bold">ACTIVE ROUTE</span>
              <span className="font-mono text-[9px] px-1 py-0.2 bg-[#E6391E] text-white font-bold">
                {activeAccount.tier}
              </span>
            </div>
            <div className="font-headline text-xs font-bold text-[#0A0A0A]">
              {activeAccount.email}
            </div>
          </div>
          <div className="flex items-center gap-2 font-mono text-[10px]">
            <span className="text-zinc-500">Claude: <strong className="text-[#E6391E]">{activeAccount.claude_weekly_percent ?? 0}%</strong></span>
            <ArrowRight className="w-3.5 h-3.5 text-[#0A0A0A] group-hover:translate-x-0.5 transition-transform" />
          </div>
        </div>
      )}

      {/* One-Line Quotas List */}
      <div className="space-y-2">
        {/* Table Column Headers */}
        <div className="grid grid-cols-12 gap-1 px-3 py-1 font-mono text-[10px] text-zinc-500 uppercase border-b border-zinc-200">
          <span className="col-span-5">Account</span>
          <span className="col-span-3 text-center">Gemini 5h / Wk</span>
          <span className="col-span-3 text-center">Claude 5h / Wk</span>
          <span className="col-span-1 text-right">View</span>
        </div>

        {loading ? (
          <div className="space-y-3">
            <div className="p-4 flex items-center justify-center bg-zinc-50 border border-zinc-200">
              <LoadingSpinner size="md" label="Querying live Google Cloud Code quota summaries..." />
            </div>
            <SkeletonList rows={4} />
          </div>
        ) : (
          <div className="space-y-1.5">
            {scores.map((s, idx) => {
              const isActive = s.is_active || s.account_name.includes('[ACTIVE]');
              const gemini5h = Math.round(s.gemini_5h_percent ?? s.five_hour_quota_percent ?? 100);
              const geminiWk = Math.round(s.gemini_weekly_percent ?? s.weekly_quota_percent ?? 0);
              const claude5h = Math.round(s.claude_5h_percent ?? 100);
              const claudeWk = Math.round(s.claude_weekly_percent ?? 0);

              return (
                <button
                  key={s.email}
                  type="button"
                  onClick={() => setSelectedAccount(s)}
                  className={`w-full text-left py-2.5 px-3 grid grid-cols-12 gap-1 items-center border transition-all cursor-pointer hover:bg-zinc-100 ${
                    isActive
                      ? 'border-[#0A0A0A] bg-zinc-50 border-2 font-bold'
                      : 'border-zinc-300 bg-white hover:border-[#0A0A0A]'
                  }`}
                >
                  {/* Account Name Column */}
                  <div className="col-span-5 flex items-center gap-1.5 min-w-0 pr-1">
                    <span className="font-mono text-[10px] text-zinc-400 shrink-0">
                      0{idx + 1}
                    </span>
                    <span className="font-headline text-xs text-[#0A0A0A] truncate">
                      {s.email.split('@')[0]}
                    </span>
                    {isActive && (
                      <span className="font-mono text-[7px] bg-[#E6391E] text-white font-bold px-1 py-0.2 shrink-0">
                        ACT
                      </span>
                    )}
                  </div>

                  {/* Gemini 5h / Weekly Column */}
                  <div className="col-span-3 text-center font-mono text-[11px]">
                    <span className="text-[#0A0A0A]">{gemini5h}%</span>
                    <span className="text-zinc-300 px-0.5">/</span>
                    <span className={geminiWk > 0 ? 'text-[#0A0A0A] font-bold' : 'text-zinc-400'}>
                      {geminiWk}%
                    </span>
                  </div>

                  {/* Claude 5h / Weekly Column */}
                  <div className="col-span-3 text-center font-mono text-[11px]">
                    <span className="text-[#0A0A0A]">{claude5h}%</span>
                    <span className="text-zinc-300 px-0.5">/</span>
                    <span
                      className={
                        claudeWk > 0
                          ? 'text-[#E6391E] font-bold'
                          : 'text-zinc-400 line-through'
                      }
                    >
                      {claudeWk}%
                    </span>
                  </div>

                  {/* Redirect Arrow Column */}
                  <div className="col-span-1 flex justify-end">
                    <ArrowRight className="w-3.5 h-3.5 text-zinc-400 group-hover:text-[#0A0A0A]" />
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="border border-zinc-300 p-3 bg-zinc-50 font-mono text-[10px] text-zinc-600 space-y-1">
        <div className="flex items-center justify-between font-bold text-[#0A0A0A]">
          <span>TAP ANY ACCOUNT ROW FOR FULL LIMITS & RESET TIMERS</span>
          <span>8 REGISTERED</span>
        </div>
        <p className="text-[9px] text-zinc-500 leading-normal">
          Quota percentages update live via Google Cloud Code telemetry. Tap an account to view full 4-way limit meters, reset deadlines, and OC-EDS mathematics.
        </p>
      </div>
    </div>
  );
};


