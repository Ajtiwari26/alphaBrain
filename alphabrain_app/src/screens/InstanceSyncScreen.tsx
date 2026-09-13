import React, { useState } from 'react';

interface Props {
  onSynced?: () => void;
}

export const InstanceSyncScreen: React.FC<Props> = ({ onSynced }) => {
  const [synced, setSynced] = useState(true);

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-4">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          CONNECT HARDWARE
        </span>
        <h2 className="text-4xl font-headline font-bold mt-2 leading-tight text-[#0A0A0A]">
          Connect
          <br />
          Instance
        </h2>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center py-10">
        {/* Viewfinder with red-orange corner brackets */}
        <div className="w-64 h-64 relative flex flex-col items-center justify-center border border-dashed border-zinc-200 bg-zinc-50/50">
          <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-[#E6391E]" />
          <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-[#E6391E]" />
          <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-[#E6391E]" />
          <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-[#E6391E]" />

          <span className="font-mono text-[10px] text-zinc-400 tracking-widest uppercase">
            {synced ? 'DEVICE PAIRED: 10BF5P2AZF0010T' : 'SCAN WORKSTATION QR'}
          </span>
          <span className="font-mono text-xs font-bold text-[#0A0A0A] mt-2">
            USB ADB SECURE TUNNEL
          </span>
          <span className="font-mono text-[10px] text-[#E6391E] mt-1">
            PORT 8000 // ACTIVE
          </span>
        </div>
      </div>

      <div
        onClick={onSynced}
        className="border border-[#0A0A0A] p-5 flex items-center justify-between hover:bg-black hover:text-white cursor-pointer transition-colors group"
      >
        <span className="font-mono text-xs text-zinc-500 group-hover:text-zinc-300">
          HARDWARE_SERIAL
        </span>
        <span className="font-mono text-xs font-bold text-[#E6391E] group-hover:text-white">
          10BF5P2AZF0010T ↗
        </span>
      </div>
    </div>
  );
};
