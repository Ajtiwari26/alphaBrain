import React, { useState } from 'react';

export const DeploymentsScreen: React.FC = () => {
  const [deployed, setDeployed] = useState(false);

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          PIPELINE
        </span>
        <h2 className="text-4xl font-headline font-bold text-[#E6391E] mt-1">
          {deployed ? 'LIVE' : 'DEPLOYING'}
        </h2>
      </div>

      <div className="flex-1 py-6 font-mono text-xs space-y-4">
        <div className="flex justify-between border-b border-zinc-200 pb-2">
          <span className="text-zinc-500">TARGET:</span>
          <span className="font-bold text-[#0A0A0A]">PRODUCTION</span>
        </div>
        <div className="flex justify-between border-b border-zinc-200 pb-2">
          <span className="text-zinc-500">COMMIT:</span>
          <span className="text-[#E6391E] font-bold">360b501</span>
        </div>
        <div className="flex justify-between border-b border-zinc-200 pb-2">
          <span className="text-zinc-500">BUILD TIME:</span>
          <span className="font-bold text-[#0A0A0A]">24.2s</span>
        </div>
        <div className="flex justify-between border-b border-zinc-200 pb-2">
          <span className="text-zinc-500">HEALTH:</span>
          <span className="font-bold text-[#0A0A0A]">100% HEALTHY</span>
        </div>

        <p className="text-zinc-400 text-[11px] mt-6 leading-relaxed">
          Optimizing static assets...
          <br />
          Generating edge functions...
          <br />
          Deployment live in 12 regions across multi-cloud edge mesh.
        </p>
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex justify-between items-center font-mono text-xs">
        <span
          onClick={() => setDeployed(true)}
          className="font-bold text-[#E6391E] underline cursor-pointer hover:text-black"
        >
          VIEW LIVE ↗
        </span>
        <span className="text-zinc-500 hover:text-black cursor-pointer">
          ROLLBACK
        </span>
      </div>
    </div>
  );
};
