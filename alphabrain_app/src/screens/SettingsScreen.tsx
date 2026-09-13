import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';

export const SettingsScreen: React.FC = () => {
  const [emergencyActive, setEmergencyActive] = useState(false);
  const [settings, setSettings] = useState({
    dispatch: true,
    opusReview: true,
    autoMerge: false,
    hardwareSync: true,
  });

  useEffect(() => {
    mobileApi
      .getEmergencyStop()
      .then((state) => setEmergencyActive(state.active))
      .catch(console.error);
  }, []);

  const toggleEmergency = async () => {
    const nextState = !emergencyActive;
    try {
      const res = await mobileApi.toggleEmergencyStop(
        nextState,
        nextState ? 'Emergency stop enabled via Founder Settings' : 'Emergency stop disengaged via Founder Settings'
      );
      setEmergencyActive(res.active);
    } catch (e) {
      console.error('Failed to toggle emergency stop:', e);
    }
  };

  const toggle = (key: keyof typeof settings) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          FOUNDER PREFERENCES & CONTROLS
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Settings
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-4">
        {/* Emergency Stop Tombstone */}
        <div
          onClick={toggleEmergency}
          className={`py-5 px-2 flex items-center justify-between cursor-pointer transition-colors ${
            emergencyActive ? 'bg-red-50 border border-[#E6391E]' : 'hover:bg-zinc-50'
          }`}
        >
          <div>
            <span className="font-medium text-base text-[#0A0A0A]">Emergency Stop Killswitch</span>
            <span className="font-mono text-[10px] text-zinc-400 block mt-0.5">
              Tombstone: ~/.alphabrain/emergency_stop.lock
            </span>
          </div>
          <span className="font-mono text-xs font-bold">
            {emergencyActive ? (
              <span className="text-[#E6391E] font-extrabold">[ LOCKED ]</span>
            ) : (
              <span className="text-zinc-500">ARMED</span>
            )}
          </span>
        </div>

        {/* Toggle 1: Dispatch */}
        <div
          onClick={() => toggle('dispatch')}
          className="py-5 px-2 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <div>
            <span className="font-medium text-base">Autonomous Dispatch</span>
            <span className="font-mono text-[10px] text-zinc-400 block mt-0.5">
              Task admission → SafetyGate → Worker lease
            </span>
          </div>
          <span className="font-mono text-xs font-bold">
            {settings.dispatch ? (
              <span className="text-[#E6391E]">[ ON ]</span>
            ) : (
              <span className="text-zinc-400">[ OFF ]</span>
            )}
          </span>
        </div>

        {/* Toggle 2: Opus Review */}
        <div
          onClick={() => toggle('opusReview')}
          className="py-5 px-2 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <div>
            <span className="font-medium text-base">Senior Opus Review</span>
            <span className="font-mono text-[10px] text-zinc-400 block mt-0.5">
              Claude Opus 4.6 Thinking mandatory SDLC gate
            </span>
          </div>
          <span className="font-mono text-xs font-bold">
            {settings.opusReview ? (
              <span className="text-[#E6391E]">[ ON ]</span>
            ) : (
              <span className="text-zinc-400">[ OFF ]</span>
            )}
          </span>
        </div>

        {/* Toggle 3: Auto Merge */}
        <div
          onClick={() => toggle('autoMerge')}
          className="py-5 px-2 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <div>
            <span className="font-medium text-base">Production Fast-Forward Merge</span>
            <span className="font-mono text-[10px] text-zinc-400 block mt-0.5">
              Atomic merge to main on unanimous review approval
            </span>
          </div>
          <span className="font-mono text-xs font-bold">
            {settings.autoMerge ? (
              <span className="text-[#E6391E]">[ ON ]</span>
            ) : (
              <span className="text-zinc-400">[ OFF ]</span>
            )}
          </span>
        </div>

        {/* Toggle 4: USB Sync */}
        <div
          onClick={() => toggle('hardwareSync')}
          className="py-5 px-2 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <div>
            <span className="font-medium text-base">USB Hardware Sync</span>
            <span className="font-mono text-[10px] text-zinc-400 block mt-0.5">
              Device 10BF5P2AZF0010T port 8000 reverse tunnel
            </span>
          </div>
          <span className="font-mono text-xs font-bold">
            {settings.hardwareSync ? (
              <span className="text-[#E6391E]">[ ON ]</span>
            ) : (
              <span className="text-zinc-400">[ OFF ]</span>
            )}
          </span>
        </div>
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 space-y-3">
        <button
          onClick={() => {
            sessionStorage.removeItem('alpha_session_stage');
            window.location.reload();
          }}
          className="w-full py-3.5 border border-[#0A0A0A] font-mono text-xs font-bold text-[#E6391E] hover:bg-black hover:text-white flex items-center justify-center gap-2 btn-tactile bg-white"
        >
          <span>REPLAY ONBOARDING & BOOT FLOW ↗</span>
        </button>

        <div className="flex items-center justify-between font-mono text-xs">
          <span className="text-zinc-500">SYSTEM VERSION</span>
          <span className="font-bold text-[#0A0A0A]">V1.0.0 // LOCOMOTIVE LIVE</span>
        </div>
      </div>
    </div>
  );
};
