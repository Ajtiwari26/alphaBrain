import React, { useState, useEffect } from 'react';
import { SelfHealingRadar } from '../types';
import { mobileApi } from '../api/client';
import { ShieldCheck, ShieldAlert, Zap, RefreshCw, CheckCircle2 } from 'lucide-react';

export const SelfHealingScreen: React.FC = () => {
  const [radar, setRadar] = useState<SelfHealingRadar | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi.getSelfHealing().then((data) => {
      setRadar(data);
      setLoading(false);
    });
  }, []);

  if (loading || !radar) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Connecting to CI/CD healing daemon...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">09 • CI/CD RADAR</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Self-Healing Engine</h1>
        </div>
        <div className="flex items-center gap-1.5 font-mono text-xs text-emerald-400 bg-emerald-950/60 px-2 py-1 rounded border border-emerald-800">
          <Zap className="w-3.5 h-3.5" />
          <span>DAEMON RUNNING</span>
        </div>
      </div>

      {/* Overview Card */}
      <div className="grid grid-cols-2 gap-3 font-mono text-xs">
        <div className="locomotive-card p-3 rounded-lg">
          <span className="text-muted text-[10px] block">ACTIVE HEALERS</span>
          <span className="font-display text-2xl font-bold text-white mt-1 block">{radar.active_healers}</span>
          <span className="text-emerald-400 text-[11px]">Gemini Pipeline Mechanic</span>
        </div>
        <div className="locomotive-card p-3 rounded-lg">
          <span className="text-muted text-[10px] block">REPAIRS (24H)</span>
          <span className="font-display text-2xl font-bold text-white mt-1 block">{radar.recent_repairs_count}</span>
          <span className="text-muted text-[11px]">Auto-synthesized diffs</span>
        </div>
      </div>

      {/* Circuit Breakers */}
      <div className="space-y-3">
        <span className="font-mono text-xs text-muted block">AUTONOMOUS CIRCUIT BREAKERS</span>
        {radar.circuit_breakers.map((cb, idx) => (
          <div key={cb.name} className="locomotive-card p-4 rounded-lg flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-accent font-bold">0{idx + 1}</span>
                <span className="font-display text-sm font-semibold text-white">{cb.name}</span>
              </div>
              <div className="font-mono text-xs text-muted mt-1">
                Threshold: {cb.threshold} failures · Current: {cb.failure_count}
              </div>
            </div>
            <div className="flex items-center gap-1.5 font-mono text-xs text-emerald-400 bg-emerald-950 px-2.5 py-1 rounded border border-emerald-800">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span className="uppercase">{cb.state}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
