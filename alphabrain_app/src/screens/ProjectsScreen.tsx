import React from 'react';

export const ProjectsScreen: React.FC = () => {
  const projects = [
    { name: 'DeployMate', statusColor: 'bg-[#E6391E]', updated: '2M AGO' },
    { name: 'AlphaBrain Core', statusColor: 'bg-[#E6391E]', updated: '14M AGO' },
    { name: 'Agent Mesh', statusColor: 'bg-zinc-300', updated: '3D AGO' },
  ];

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          PORTFOLIO
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Projects
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-4">
        {projects.map((p) => (
          <div
            key={p.name}
            className="py-6 px-1 flex flex-col justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-2xl font-headline font-bold text-[#0A0A0A]">
                {p.name}
              </h3>
              <span className={`w-2.5 h-2.5 rounded-full ${p.statusColor}`} />
            </div>
            <span className="font-mono text-[10px] text-zinc-400 mt-3 uppercase">
              LAST UPDATE: {p.updated}
            </span>
          </div>
        ))}
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex items-center justify-between font-mono text-xs">
        <span className="text-zinc-500">ACTIVE WORKSPACES</span>
        <span className="font-bold text-[#0A0A0A]">3 REPOSITORIES</span>
      </div>
    </div>
  );
};
