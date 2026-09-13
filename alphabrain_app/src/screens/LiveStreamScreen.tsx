import React, { useState } from 'react';

export const LiveStreamScreen: React.FC = () => {
  const [paused, setPaused] = useState(false);

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
          TERMINAL FEED
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Execution Log
        </h2>
      </div>

      <div className="flex-1 p-4 font-mono text-[11px] leading-relaxed overflow-y-auto bg-zinc-50 border border-[#0A0A0A] my-4">
        <p>
          <span className="text-[#0A0A0A] font-bold">[SYS]</span> Initializing worktree WT-042...
        </p>
        <p className="mt-2">
          <span className="text-[#E6391E] font-bold">[AGENT]</span> Reading design.md specification
        </p>
        <p className="mt-2">
          <span className="text-[#E6391E] font-bold">[AGENT]</span> Tracing pure vector Alpha SVG
        </p>
        <p className="mt-2">
          <span className="text-[#0A0A0A] font-bold">[SYS]</span> Render check passed: 200 OK
        </p>
        <p className="mt-2">
          <span className="text-[#E6391E] font-bold">[AGENT]</span> Porting DeployMate Locomotive white tokens
        </p>
        <p className="mt-2">
          <span className="text-[#0A0A0A] font-bold">[SYS]</span> Synchronizing with USB device 10BF5P2AZF0010T...
        </p>
        <p className="mt-2 text-zinc-400">
          [SYS] Awaiting senior gate approval_
        </p>
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex gap-3">
        <button
          onClick={() => setPaused(!paused)}
          className="flex-1 border border-[#0A0A0A] py-3 font-mono text-xs font-bold hover:bg-black hover:text-white transition-colors"
        >
          {paused ? 'RESUME' : 'PAUSE'}
        </button>
        <button className="flex-1 bg-[#E6391E] text-white py-3 font-mono text-xs font-bold hover:bg-black transition-colors">
          INTERRUPT
        </button>
      </div>
    </div>
  );
};
