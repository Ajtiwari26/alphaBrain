import React, { useState, useEffect } from 'react';
import { EmergencyStopState } from '../types';
import { mobileApi } from '../api/client';
import { ShieldAlert, ShieldCheck, Power, AlertOctagon, CheckCircle2 } from 'lucide-react';

export const EmergencyStopScreen: React.FC = () => {
  const [stopState, setStopState] = useState<EmergencyStopState | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggleLoading, setToggleLoading] = useState(false);

  const loadState = async () => {
    try {
      const data = await mobileApi.getEmergencyStop();
      setStopState(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadState();
  }, []);

  const handleToggle = async (enable: boolean) => {
    setToggleLoading(true);
    try {
      const updated = await mobileApi.toggleEmergencyStop(
        enable,
        enable ? 'Manual emergency lock by Founder on iQOO 12' : 'Resumed by Founder'
      );
      setStopState(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setToggleLoading(false);
    }
  };

  if (loading || !stopState) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Querying emergency stop tombstone...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-red-500 uppercase tracking-widest">14 // FOUNDER CONTROL</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Emergency Kill Switch</h1>
        </div>
        <span className={`font-mono text-xs px-2.5 py-1 rounded font-semibold uppercase ${
          stopState.active
            ? 'bg-red-950 text-red-400 border border-red-800'
            : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
        }`}>
          {stopState.active ? 'STOP ENGAGED' : 'ARMED & READY'}
        </span>
      </div>

      {/* Emergency Status Card */}
      <div className={`locomotive-card p-6 rounded-xl text-center space-y-3 ${
        stopState.active ? 'border-red-600 bg-red-950/20' : 'border-card-border'
      }`}>
        <div className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto ${
          stopState.active ? 'bg-red-600/20 text-red-500 border border-red-500' : 'bg-slate-800 text-slate-400'
        }`}>
          <AlertOctagon className="w-8 h-8" />
        </div>

        <h3 className="font-display text-lg font-bold text-white">
          {stopState.active ? 'Autonomous Fleet Frozen' : 'System Quiescence Invariant'}
        </h3>
        <p className="font-mono text-xs text-muted max-w-xs mx-auto">
          {stopState.active
            ? 'All worktree worker loops, triage auto-promotions, and deployments are paused.'
            : 'Engaging the kill switch immediately creates the emergency tombstone lock file.'}
        </p>

        {stopState.active ? (
          <button
            disabled={toggleLoading}
            onClick={() => handleToggle(false)}
            className="w-full py-3.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-bold transition-all"
          >
            {toggleLoading ? 'Resuming...' : 'DISENGAGE EMERGENCY STOP & RESUME'}
          </button>
        ) : (
          <button
            disabled={toggleLoading}
            onClick={() => handleToggle(true)}
            className="w-full py-3.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-mono text-xs font-bold transition-all shadow-lg shadow-red-950/50"
          >
            {toggleLoading ? 'Engaging...' : 'ENGAGE FOUNDER EMERGENCY STOP'}
          </button>
        )}
      </div>

      {/* Lockfile Details */}
      <div className="locomotive-card p-4 rounded-lg space-y-2 font-mono text-xs">
        <span className="text-muted block text-[10px] uppercase tracking-wider">TOMBSTONE LOCKFILE DETAILS</span>
        <div className="p-2.5 rounded bg-background border border-card-border text-slate-300 space-y-1">
          <div className="flex justify-between">
            <span className="text-muted">Target Path:</span>
            <span className="truncate max-w-[200px]">{stopState.lock_file}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Status:</span>
            <span className={stopState.active ? 'text-red-400' : 'text-emerald-400'}>
              {stopState.active ? 'LOCKED' : 'UNLOCKED'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
