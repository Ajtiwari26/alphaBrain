import React, { useState, useEffect } from 'react';
import { SprintFleetOverview } from '../types';
import { mobileApi } from '../api/client';
import { Cpu, Activity, Clock, Sliders, CheckCircle2 } from 'lucide-react';

export const SprintFleetScreen: React.FC = () => {
  const [fleet, setFleet] = useState<SprintFleetOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi.getSprintFleet().then((data) => {
      setFleet(data);
      setLoading(false);
    });
  }, []);

  if (loading || !fleet) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Loading autonomous fleet status...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">06 // WORKER SWARM</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Autonomous Fleet</h1>
        </div>
        <div className="flex items-center gap-1 font-mono text-xs text-emerald-400 bg-emerald-950/60 px-2 py-1 rounded border border-emerald-800">
          <Activity className="w-3.5 h-3.5 animate-pulse" />
          <span>{fleet.active_workers}/{fleet.max_workers} ACTIVE</span>
        </div>
      </div>

      {/* Adaptive Hardware Throttle */}
      <div className="locomotive-card p-4 rounded-lg space-y-2">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-muted flex items-center gap-1.5">
            <Sliders className="w-4 h-4 text-accent" /> ADAPTIVE HARDWARE THROTTLE
          </span>
          <span className="text-white font-semibold">{fleet.adaptive_throttle_factor * 100}% CAPACITY</span>
        </div>
        <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-card-border">
          <div
            className="bg-accent h-full rounded-full transition-all duration-500"
            style={{ width: `${fleet.adaptive_throttle_factor * 100}%` }}
          />
        </div>
        <div className="text-[11px] font-mono text-muted flex justify-between">
          <span>Battery Thermal Protection: ACTIVE</span>
          <span>MacBook Pro M3 Max Headroom</span>
        </div>
      </div>

      {/* Worker Slots Grid */}
      <div className="space-y-3">
        <span className="font-mono text-xs text-muted block">WORKTREE EXECUTOR SLOTS</span>
        {fleet.slots.map((slot, i) => (
          <div key={slot.worker_id} className="locomotive-card p-4 rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-accent font-bold">SLOT 0{i + 1}</span>
                <span className="font-mono text-xs text-white font-medium">{slot.worker_id}</span>
              </div>
              <span className={`font-mono text-[10px] px-2 py-0.5 rounded uppercase ${
                slot.status === 'running'
                  ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                  : 'bg-slate-800 text-muted'
              }`}>
                {slot.status}
              </span>
            </div>

            {slot.current_task_id ? (
              <div className="p-2.5 rounded bg-background border border-card-border space-y-1.5 font-mono text-xs">
                <div className="flex items-center justify-between text-slate-300">
                  <span className="text-muted text-[10px]">ACTIVE TASK:</span>
                  <span className="text-accent">{slot.current_task_id}</span>
                </div>
                <div className="flex items-center justify-between text-muted text-[11px]">
                  <span>Worktree: {slot.worktree_slug}</span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" /> {Math.round(slot.uptime_seconds / 60)}m uptime
                  </span>
                </div>
              </div>
            ) : (
              <div className="p-3 rounded bg-background/50 border border-dashed border-card-border text-center font-mono text-xs text-muted">
                Slot idle. Waiting for next approved task in triage queue.
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
