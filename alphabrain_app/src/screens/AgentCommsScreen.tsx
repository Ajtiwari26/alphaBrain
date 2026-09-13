import React from 'react';

export const AgentCommsScreen: React.FC = () => {
  const agents = [
    { name: 'Worker AGY-1', status: 'ACTIVE', statusStyle: 'bg-[#E6391E] text-white', nameStyle: 'text-[#E6391E]' },
    { name: 'Research AGY-2', status: 'IDLE', statusStyle: 'text-zinc-400', nameStyle: 'text-[#0A0A0A]' },
    { name: 'Reviewer Opus', status: 'DEBATING', statusStyle: 'text-[#E6391E] font-bold', nameStyle: 'text-[#0A0A0A]' },
    { name: 'Eva Voice CTO', status: 'SYNTHESIZING', statusStyle: 'bg-[#0A0A0A] text-white', nameStyle: 'text-[#0A0A0A]' },
  ];

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          MESH PROTOCOL
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Agent Hub
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-3">
        {agents.map((a) => (
          <div key={a.name} className="py-5 px-1">
            <div className="flex items-center justify-between mb-3">
              <span className={`font-bold text-base ${a.nameStyle}`}>{a.name}</span>
              <span className={`font-mono text-[10px] uppercase px-1.5 py-0.5 ${a.statusStyle}`}>
                {a.status}
              </span>
            </div>
            <div className="flex items-center gap-4 font-mono text-xs">
              <span className="text-[#0A0A0A] font-bold underline cursor-pointer hover:text-[#E6391E]">
                CHAT
              </span>
              <span className="text-zinc-400 cursor-pointer hover:text-black">
                CALL
              </span>
              <span className="text-zinc-400 cursor-pointer hover:text-black">
                BRIEFING
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="border border-[#0A0A0A] p-4 bg-zinc-50">
        <div className="flex items-center justify-between font-mono text-xs">
          <span className="text-zinc-500">VOICE CTO SYNTHESIS</span>
          <span className="font-bold text-[#E6391E]">EVA 2.0 // READY</span>
        </div>
      </div>
    </div>
  );
};
