import React, { useState, useEffect } from 'react';
import { desktopApi } from '../api/client';
import { EmergencyStopState } from '../types';
import { AlertOctagon, FileText } from 'lucide-react';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SkeletonCard } from '../components/ui/Skeleton';

export const EmergencyStopScreen: React.FC = () => {
  const [stopState, setStopState] = useState<EmergencyStopState | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggleLoading, setToggleLoading] = useState(false);

  const loadState = async () => {
    try {
      const data = await desktopApi.getEmergencyStop();
      setStopState(data);
    } catch (e) {
      console.error('Failed to load emergency stop state:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadState();
  }, []);

  const handleToggle = async (enable: boolean) => {
    const message = enable
      ? 'HALT FLEET CONFIRMATION:\nAre you sure you want to engage the Emergency Stop?\nThis will immediately halt all autonomous workers, worktrees, and cloud leases.'
      : 'RESUME FLEET CONFIRMATION:\nAre you sure you want to resume cluster operations?';
    if (typeof window !== 'undefined' && !window.confirm(message)) {
      return;
    }
    setToggleLoading(true);
    try {
      const updated = await desktopApi.toggleEmergencyStop(
        enable,
        enable
          ? 'Emergency stop engaged by Founder Ajay from Mac Command Node'
          : 'Resumed by Founder Ajay from Mac Command Node'
      );
      setStopState(updated);
    } catch (err) {
      console.error('Failed to toggle emergency stop:', err);
    } finally {
      setToggleLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto p-8 space-y-6 animate-screen-enter">
        <div className="p-16 text-center border border-[#0A0A0A] bg-white flex flex-col items-center justify-center gap-4">
          <LoadingSpinner size="lg" label="Querying emergency stop tombstone status..." />
        </div>
      </div>
    );
  }

  if (!stopState) {
    return (
      <div className="max-w-7xl mx-auto p-8 space-y-6">
        <div className="border border-[#0A0A0A] bg-neutral-50 p-8 text-center space-y-3">
          <div className="font-mono text-xs text-[#E6391E] font-bold uppercase tracking-widest">
            OFFLINE // BACKEND SERVICE UNREACHABLE
          </div>
          <p className="font-mono text-xs text-neutral-600">
            Cannot reach emergency tombstone service. Local safe state active.
          </p>
          <button
            onClick={loadState}
            className="px-4 py-2 border border-[#0A0A0A] bg-white font-mono text-xs font-bold hover:bg-neutral-100"
          >
            RETRY CONNECTION
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-6 animate-screen-enter">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#E6391E] font-bold uppercase tracking-widest">
              MC-14 // FOUNDER DIRECT CONTROL
            </span>
            <span className="text-neutral-300">•</span>
            <span className="font-mono text-xs text-neutral-500 uppercase">
              HARDWARE & PROCESS QUIESCENCE
            </span>
          </div>
          <h1 className="text-3xl font-bold font-sans tracking-tight mt-1 text-[#0A0A0A]">
            Emergency Kill Switch
          </h1>
          <p className="font-mono text-xs text-neutral-500 mt-1">
            Global emergency shutdown mechanism for all autonomous workers, triage pipelines, and deployments
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`font-mono text-xs px-3 py-1.5 font-bold uppercase border transition-smooth ${
              stopState.active
                ? 'bg-red-50 text-[#E6391E] border-red-300 animate-pulse'
                : 'bg-emerald-50 text-emerald-800 border-emerald-300'
            }`}
          >
            {stopState.active ? 'STOP ENGAGED' : 'ARMED & READY'}
          </span>
        </div>
      </div>

      {/* Main Status Callout Hero */}
      <div
        className={`border-2 p-8 text-center space-y-4 transition-smooth hover-lift ${
          stopState.active
            ? 'border-[#E6391E] bg-red-50/30'
            : 'border-[#0A0A0A] bg-white'
        }`}
      >
        <div
          className={`w-20 h-20 border-2 flex items-center justify-center mx-auto transition-transform duration-300 hover:scale-105 ${
            stopState.active
              ? 'border-[#E6391E] bg-red-100 text-[#E6391E]'
              : 'border-[#0A0A0A] bg-neutral-100 text-[#0A0A0A]'
          }`}
        >
          <AlertOctagon className="w-10 h-10" />
        </div>

        <div>
          <h2 className="text-2xl font-bold font-sans text-[#0A0A0A]">
            {stopState.active ? 'Autonomous Fleet Frozen' : 'System Quiescence Invariant Ready'}
          </h2>
          <p className="font-mono text-xs text-neutral-600 max-w-xl mx-auto mt-2 leading-relaxed">
            {stopState.active
              ? 'All worker dispatch loops, git worktree task executors, triage promotions, and deployment pipelines have been halted immediately.'
              : 'Engaging the kill switch immediately creates the atomic tombstone lock file on host filesystem.'}
          </p>
        </div>

        <div className="pt-4 max-w-md mx-auto">
          {stopState.active ? (
            <button
              disabled={toggleLoading}
              onClick={() => handleToggle(false)}
              className="w-full py-4 border border-emerald-700 bg-emerald-600 hover:bg-emerald-700 text-white font-mono text-xs font-bold transition-smooth btn-tactile hover-lift active:scale-95 uppercase tracking-wider flex items-center justify-center gap-2"
            >
              {toggleLoading ? (
                <>
                  <LoadingSpinner size="sm" color="#FFFFFF" />
                  <span>RESUMING...</span>
                </>
              ) : (
                'DISENGAGE EMERGENCY STOP & RESUME ALL FLEET WORKERS'
              )}
            </button>
          ) : (
            <button
              disabled={toggleLoading}
              onClick={() => handleToggle(true)}
              className="w-full py-4 border border-[#E6391E] bg-[#E6391E] hover:bg-red-700 text-white font-mono text-xs font-bold transition-smooth btn-tactile hover-lift active:scale-95 uppercase tracking-wider shadow-sm flex items-center justify-center gap-2"
            >
              {toggleLoading ? (
                <>
                  <LoadingSpinner size="sm" color="#FFFFFF" />
                  <span>ENGAGING...</span>
                </>
              ) : (
                'ENGAGE FOUNDER EMERGENCY STOP'
              )}
            </button>
          )}
        </div>
      </div>

      {/* Tombstone Lockfile Diagnostics */}
      <div className="border border-[#0A0A0A] bg-white p-6 space-y-3 font-mono text-xs">
        <div className="flex items-center gap-2 text-neutral-500 text-[11px] uppercase tracking-wider border-b border-neutral-200 pb-2">
          <FileText className="w-4 h-4 text-[#0A0A0A]" />
          <span>TOMBSTONE LOCKFILE DIAGNOSTICS</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div className="border border-neutral-200 bg-neutral-50 p-3 space-y-1">
            <span className="text-[10px] text-neutral-400 uppercase block">Lockfile Target Path</span>
            <span className="font-bold text-[#0A0A0A] break-all">{stopState.lock_file}</span>
          </div>

          <div className="border border-neutral-200 bg-neutral-50 p-3 space-y-1">
            <span className="text-[10px] text-neutral-400 uppercase block">Lockfile Status</span>
            <span className={`font-bold ${stopState.active ? 'text-[#E6391E]' : 'text-emerald-700'}`}>
              {stopState.active ? 'LOCKED (TOMBSTONE ACTIVE)' : 'UNLOCKED (NOMINAL)'}
            </span>
          </div>

          <div className="border border-neutral-200 bg-neutral-50 p-3 space-y-1">
            <span className="text-[10px] text-neutral-400 uppercase block">Triggered By</span>
            <span className="font-bold text-[#0A0A0A]">{stopState.triggered_by}</span>
          </div>

          <div className="border border-neutral-200 bg-neutral-50 p-3 space-y-1">
            <span className="text-[10px] text-neutral-400 uppercase block">Operational Directive</span>
            <span className="font-bold text-[#0A0A0A]">{stopState.reason}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
