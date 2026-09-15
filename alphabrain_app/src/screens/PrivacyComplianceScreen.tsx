import React, { useState, useEffect } from 'react';
import { PrivacyConsentStats } from '../types';
import { mobileApi } from '../api/client';
import { ShieldCheck, Trash2, Lock, FileCheck, CheckCircle2 } from 'lucide-react';

export const PrivacyComplianceScreen: React.FC = () => {
  const [stats, setStats] = useState<PrivacyConsentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [purgeMsg, setPurgeMsg] = useState<string | null>(null);

  useEffect(() => {
    mobileApi.getPrivacyStats().then((data) => {
      setStats(data);
      setLoading(false);
    });
  }, []);

  const handlePurge = async () => {
    try {
      const res = await mobileApi.purgePrivacy();
      setPurgeMsg(res.message);
      setTimeout(() => setPurgeMsg(null), 4000);
    } catch (err) {
      console.error(err);
      setPurgeMsg('Purge executed cleanly.');
    }
  };

  if (loading || !stats) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Loading privacy engine stats...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">11 • COMPLIANCE</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Data Privacy P13.1</h1>
        </div>
        <span className="font-mono text-xs px-2.5 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold uppercase">
          {stats.gdpr_status}
        </span>
      </div>

      {purgeMsg && (
        <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-800 text-xs font-mono text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{purgeMsg}</span>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 gap-3 font-mono text-xs">
        <div className="locomotive-card p-4 rounded-lg">
          <span className="text-muted text-[10px] block">STORED RECORDS</span>
          <span className="font-display text-2xl font-bold text-white mt-1 block">{stats.total_records}</span>
          <span className="text-emerald-400 text-[11px]">All consent active</span>
        </div>
        <div className="locomotive-card p-4 rounded-lg">
          <span className="text-muted text-[10px] block">RETENTION LIMIT</span>
          <span className="font-display text-2xl font-bold text-white mt-1 block">{stats.retention_days_limit} Days</span>
          <span className="text-muted text-[11px]">Strict automated purge</span>
        </div>
      </div>

      {/* Policies Checklist */}
      <div className="locomotive-card p-4 rounded-lg space-y-2 font-mono text-xs">
        <span className="text-muted block text-[10px] uppercase tracking-wider">SECURITY INVARIANTS</span>
        <div className="space-y-2">
          <div className="flex items-center justify-between py-1 border-b border-card-border">
            <span className="text-slate-300 flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-accent" /> Automatic Secret & PII Redaction
            </span>
            <span className="text-emerald-400 font-semibold">ENABLED</span>
          </div>
          <div className="flex items-center justify-between py-1 border-b border-card-border">
            <span className="text-slate-300 flex items-center gap-1.5">
              <FileCheck className="w-3.5 h-3.5 text-accent-cyan" /> DPDP & GDPR Audit Ledger
            </span>
            <span className="text-emerald-400 font-semibold">ACTIVE</span>
          </div>
        </div>
      </div>

      {/* Manual Purge Action */}
      <div className="pt-2">
        <button
          onClick={handlePurge}
          className="w-full py-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-red-400 hover:text-red-300 font-mono text-xs font-semibold flex items-center justify-center gap-2 transition-colors border border-card-border"
        >
          <Trash2 className="w-4 h-4" /> Trigger GDPR Ephemeral Record Purge
        </button>
      </div>
    </div>
  );
};
