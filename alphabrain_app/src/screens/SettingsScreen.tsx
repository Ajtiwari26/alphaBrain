import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import {
  ShieldAlert,
  ShieldCheck,
  Cpu,
  GitBranch,
  Smartphone,
  Lock,
  RotateCcw,
  Check,
  AlertTriangle,
  Server,
  Zap,
  ChevronRight,
  X,
  ExternalLink,
} from 'lucide-react';

interface Props {
  onNavigateToScreen?: (screenId: string) => void;
}

export const SettingsScreen: React.FC<Props> = ({ onNavigateToScreen }) => {
  const [emergencyActive, setEmergencyActive] = useState(false);
  const [emergencyReason, setEmergencyReason] = useState('Founder manual killswitch engaged');
  const [emergencyModalOpen, setEmergencyModalOpen] = useState(false);
  const [togglingEmergency, setTogglingEmergency] = useState(false);
  const [loading, setLoading] = useState(true);

  const [settings, setSettings] = useState({
    safetyGate: true,
    opusReview: true,
    autoMerge: false,
    hardwareSync: true,
    strictIsolation: true,
  });

  useEffect(() => {
    mobileApi
      .getEmergencyStop()
      .then((state) => {
        setEmergencyActive(state.active);
        if (state.reason) setEmergencyReason(state.reason);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to get emergency stop status:', err);
        setLoading(false);
      });
  }, []);

  const handleToggleEmergency = async () => {
    setTogglingEmergency(true);
    const nextState = !emergencyActive;
    try {
      const res = await mobileApi.toggleEmergencyStop(
        nextState,
        nextState
          ? emergencyReason || 'Emergency stop enabled via Founder Settings'
          : 'Emergency stop disengaged via Founder Settings'
      );
      setEmergencyActive(res.active);
      setEmergencyModalOpen(false);
    } catch (e) {
      console.error('Failed to toggle emergency stop:', e);
    } finally {
      setTogglingEmergency(false);
    }
  };

  const toggle = (key: keyof typeof settings) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh] animate-screen-enter pb-16">
      {/* Top Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase flex items-center gap-1.5">
            <Lock className="w-3 h-3 text-[#E6391E]" />
            FOUNDER PREFERENCES & POLICIES
          </span>
          <span className="font-mono text-[10px] font-bold px-2 py-0.5 border border-black bg-black text-white">
            MASTER AUTH
          </span>
        </div>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Settings
        </h2>
        <p className="font-sans text-xs text-zinc-500 mt-0.5">
          System-wide governance policies, emergency killswitch, model quota routing, and USB hardware sync.
        </p>
      </div>

      {/* Emergency Stop Hero Card */}
      <div
        onClick={() => setEmergencyModalOpen(true)}
        className={`my-3 p-4 border-2 cursor-pointer transition-colors card-tactile ${
          emergencyActive
            ? 'border-[#E6391E] bg-red-50 text-[#E6391E]'
            : 'border-[#0A0A0A] bg-zinc-50 hover:bg-zinc-100'
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={`p-2 border ${
                emergencyActive
                  ? 'border-[#E6391E] bg-[#E6391E] text-white'
                  : 'border-[#0A0A0A] bg-white text-[#0A0A0A]'
              }`}
            >
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-headline font-bold text-base text-[#0A0A0A]">
                  Emergency Stop Killswitch
                </h4>
                <span
                  className={`font-mono text-[10px] font-black px-2 py-0.5 border uppercase ${
                    emergencyActive
                      ? 'border-[#E6391E] bg-[#E6391E] text-white animate-pulse'
                      : 'border-emerald-600 bg-emerald-50 text-emerald-700'
                  }`}
                >
                  {emergencyActive ? 'LOCKED / HALTED' : 'ARMED / ONLINE'}
                </span>
              </div>
              <p className="font-mono text-[10px] text-zinc-500 mt-0.5">
                Tombstone: ~/.alphabrain/emergency_stop.lock
              </p>
            </div>
          </div>
          <ChevronRight className="w-5 h-5 text-zinc-400 self-center" />
        </div>
        {emergencyActive && (
          <div className="mt-2 pt-2 border-t border-red-200 font-mono text-[11px] text-[#E6391E]">
            REASON: {emergencyReason}
          </div>
        )}
      </div>

      {/* Active Model & Quota Switcher Shortcut */}
      <div className="border border-[#0A0A0A] p-3.5 bg-white mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 border border-zinc-200 bg-zinc-50">
            <Cpu className="w-4 h-4 text-[#E6391E]" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-xs font-bold text-[#0A0A0A]">
                OC-EDS Model Router
              </span>
              <span className="font-mono text-[9px] font-bold px-1.5 py-0.5 border border-emerald-600 bg-emerald-50 text-emerald-700">
                ACTIVE
              </span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500 block">
              6 Gemini Pro Accounts • Claude Opus 4.6 Thinking
            </span>
          </div>
        </div>
        <button
          onClick={() => onNavigateToScreen && onNavigateToScreen('model_router')}
          className="font-mono text-[11px] font-bold text-[#E6391E] underline hover:text-black flex items-center gap-1"
        >
          <span>QUOTAS</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Autonomous SDLC Policy Toggles */}
      <div className="flex-1 flex flex-col divide-y divide-zinc-200 border border-[#0A0A0A] bg-zinc-50/50 mb-3 overflow-y-auto max-h-[42vh]">
        {/* Policy 1: Deterministic SafetyGate */}
        <div
          onClick={() => toggle('safetyGate')}
          className="p-3.5 flex items-center justify-between bg-white hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <div className="flex-1 pr-3">
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span className="font-bold text-xs text-[#0A0A0A]">
                Deterministic SafetyGate (I-2)
              </span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500 block mt-0.5">
              Strictly blocks forbidden paths (alpha_meet/), secret leaks, & high blast-radius diffs.
            </span>
          </div>
          <span
            className={`font-mono text-xs font-bold px-2 py-0.5 border ${
              settings.safetyGate
                ? 'border-[#E6391E] bg-red-50 text-[#E6391E]'
                : 'border-zinc-300 text-zinc-400 bg-zinc-100'
            }`}
          >
            {settings.safetyGate ? '[ ON ]' : '[ OFF ]'}
          </span>
        </div>

        {/* Policy 2: Claude Opus Senior Review */}
        <div
          onClick={() => toggle('opusReview')}
          className="p-3.5 flex items-center justify-between bg-white hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <div className="flex-1 pr-3">
            <div className="flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-[#E6391E]" />
              <span className="font-bold text-xs text-[#0A0A0A]">
                Mandatory Claude Opus 4.6 (Thinking) Gate
              </span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500 block mt-0.5">
              2-Round debate between Gemini 3.1 Pro High and Claude Opus before PR promotion.
            </span>
          </div>
          <span
            className={`font-mono text-xs font-bold px-2 py-0.5 border ${
              settings.opusReview
                ? 'border-[#E6391E] bg-red-50 text-[#E6391E]'
                : 'border-zinc-300 text-zinc-400 bg-zinc-100'
            }`}
          >
            {settings.opusReview ? '[ ON ]' : '[ OFF ]'}
          </span>
        </div>

        {/* Policy 3: Fast-Forward Merge */}
        <div
          onClick={() => toggle('autoMerge')}
          className="p-3.5 flex items-center justify-between bg-white hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <div className="flex-1 pr-3">
            <div className="flex items-center gap-1.5">
              <GitBranch className="w-4 h-4 text-[#0A0A0A]" />
              <span className="font-bold text-xs text-[#0A0A0A]">
                Atomic Fast-Forward Merge (I-5)
              </span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500 block mt-0.5">
              Zero manual direct edits; only unanimous review-approved worker worktrees merge.
            </span>
          </div>
          <span
            className={`font-mono text-xs font-bold px-2 py-0.5 border ${
              settings.autoMerge
                ? 'border-[#E6391E] bg-red-50 text-[#E6391E]'
                : 'border-zinc-300 text-zinc-400 bg-zinc-100'
            }`}
          >
            {settings.autoMerge ? '[ ON ]' : '[ OFF ]'}
          </span>
        </div>

        {/* Policy 4: Hardware USB Sync */}
        <div
          onClick={() => toggle('hardwareSync')}
          className="p-3.5 flex items-center justify-between bg-white hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <div className="flex-1 pr-3">
            <div className="flex items-center gap-1.5">
              <Smartphone className="w-4 h-4 text-[#E6391E]" />
              <span className="font-bold text-xs text-[#0A0A0A]">
                USB Hardware Companion Link
              </span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500 block mt-0.5">
              Target Device 10BF5P2AZF0010T reverse tunnel on tcp:8000.
            </span>
          </div>
          <span
            className={`font-mono text-xs font-bold px-2 py-0.5 border ${
              settings.hardwareSync
                ? 'border-[#E6391E] bg-red-50 text-[#E6391E]'
                : 'border-zinc-300 text-zinc-400 bg-zinc-100'
            }`}
          >
            {settings.hardwareSync ? '[ ON ]' : '[ OFF ]'}
          </span>
        </div>
      </div>

      {/* Replay Onboarding Button & Footer */}
      <div className="border-t border-[#0A0A0A] pt-3 space-y-2">
        <button
          onClick={() => {
            sessionStorage.removeItem('alphabrain_session_token');
            sessionStorage.removeItem('alpha_session_stage');
            window.location.reload();
          }}
          className="w-full py-3 border border-[#0A0A0A] font-mono text-xs font-bold text-[#E6391E] hover:bg-black hover:text-white flex items-center justify-center gap-2 btn-tactile bg-white transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>REPLAY ONBOARDING & SECURITY BOOT ↗</span>
        </button>

        <div className="flex items-center justify-between font-mono text-[11px] text-zinc-500 px-1">
          <span>HOST: 0.0.0.0:8000</span>
          <span className="font-bold text-[#0A0A0A]">V1.0.0 • SWISS BRUTALIST</span>
        </div>
      </div>

      {/* Emergency Stop Modal Dialog */}
      {emergencyModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-white border-t-2 sm:border-2 border-[#E6391E] w-full max-w-md p-5 space-y-4 shadow-2xl animate-screen-enter">
            <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-3">
              <div className="flex items-center gap-2 text-[#E6391E]">
                <ShieldAlert className="w-5 h-5" />
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-[#0A0A0A]">
                  EMERGENCY STOP GOVERNANCE
                </span>
              </div>
              <button
                onClick={() => setEmergencyModalOpen(false)}
                className="w-7 h-7 border border-[#0A0A0A] flex items-center justify-center hover:bg-black hover:text-white transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <p className="font-sans text-xs text-zinc-700">
                {emergencyActive
                  ? 'Disengaging the emergency stop will remove ~/.alphabrain/emergency_stop.lock and re-enable autonomous swarm triage and worker execution cycles.'
                  : 'Engaging the emergency stop writes an atomic lock tombstone at ~/.alphabrain/emergency_stop.lock, immediately halting all autonomous AGY workers, triage queue leases, and external API dispatches.'}
              </p>

              <div>
                <label className="text-[10px] text-zinc-500 uppercase block mb-1">
                  AUDIT LOG REASON:
                </label>
                <input
                  type="text"
                  value={emergencyReason}
                  onChange={(e) => setEmergencyReason(e.target.value)}
                  className="w-full p-2 text-xs font-mono bg-zinc-50 border border-[#0A0A0A] focus:outline-none focus:bg-white"
                />
              </div>
            </div>

            <div className="border-t border-zinc-200 pt-3 flex gap-2">
              <button
                onClick={() => setEmergencyModalOpen(false)}
                disabled={togglingEmergency}
                className="flex-1 py-3 border border-[#0A0A0A] font-mono text-xs font-bold hover:bg-zinc-100 transition-colors"
              >
                CANCEL
              </button>
              <button
                onClick={handleToggleEmergency}
                disabled={togglingEmergency}
                className={`flex-1 py-3 font-mono text-xs font-bold text-white transition-colors flex items-center justify-center gap-1.5 ${
                  emergencyActive
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-[#E6391E] hover:bg-black'
                }`}
              >
                {togglingEmergency ? (
                  <LoadingSpinner size="sm" />
                ) : emergencyActive ? (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    <span>DISENGAGE STOP</span>
                  </>
                ) : (
                  <>
                    <ShieldAlert className="w-3.5 h-3.5" />
                    <span>ENGAGE STOP</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
