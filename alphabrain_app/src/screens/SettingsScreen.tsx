import React, { useState } from 'react';

export const SettingsScreen: React.FC = () => {
  const [settings, setSettings] = useState({
    dispatch: true,
    opusReview: true,
    autoMerge: false,
    hardwareSync: true,
  });

  const toggle = (key: keyof typeof settings) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          PREFERENCES
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Settings
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-4">
        {/* Toggle 1 */}
        <div
          onClick={() => toggle('dispatch')}
          className="py-6 px-1 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <span className="font-medium text-base">Autonomous Dispatch</span>
          <span className="font-mono text-xs font-bold">
            {settings.dispatch ? (
              <span className="text-[#E6391E]">[ ON ] / OFF</span>
            ) : (
              <span className="text-zinc-400">ON / [ OFF ]</span>
            )}
          </span>
        </div>

        {/* Toggle 2 */}
        <div
          onClick={() => toggle('opusReview')}
          className="py-6 px-1 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <span className="font-medium text-base">Senior Opus Review</span>
          <span className="font-mono text-xs font-bold">
            {settings.opusReview ? (
              <span className="text-[#E6391E]">[ ON ] / OFF</span>
            ) : (
              <span className="text-zinc-400">ON / [ OFF ]</span>
            )}
          </span>
        </div>

        {/* Toggle 3 */}
        <div
          onClick={() => toggle('autoMerge')}
          className="py-6 px-1 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <span className="font-medium text-base">Vercel Auto-Merge</span>
          <span className="font-mono text-xs font-bold">
            {settings.autoMerge ? (
              <span className="text-[#E6391E]">[ ON ] / OFF</span>
            ) : (
              <span className="text-zinc-400">ON / [ OFF ]</span>
            )}
          </span>
        </div>

        {/* Toggle 4 */}
        <div
          onClick={() => toggle('hardwareSync')}
          className="py-6 px-1 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
        >
          <span className="font-medium text-base">USB Hardware Sync</span>
          <span className="font-mono text-xs font-bold">
            {settings.hardwareSync ? (
              <span className="text-[#E6391E]">[ ON ] / OFF</span>
            ) : (
              <span className="text-zinc-400">ON / [ OFF ]</span>
            )}
          </span>
        </div>
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex items-center justify-between font-mono text-xs">
        <span className="text-zinc-500">VERSION</span>
        <span className="font-bold text-[#0A0A0A]">V1.0.0 // LOCOMOTIVE</span>
      </div>
    </div>
  );
};
