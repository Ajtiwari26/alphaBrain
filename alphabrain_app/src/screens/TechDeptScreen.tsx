import React from 'react';

interface Props {
  onNavigateTriage?: () => void;
  onNavigateWorktrees?: () => void;
  onNavigateDeployments?: () => void;
}

export const TechDeptScreen: React.FC<Props> = ({
  onNavigateTriage,
  onNavigateWorktrees,
  onNavigateDeployments,
}) => {
  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
          DEPT // 01
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Tech Dept
        </h2>
      </div>

      <div className="flex-1 flex flex-col justify-around divide-y divide-[#0A0A0A] my-4">
        <div
          onClick={onNavigateTriage}
          className="py-6 flex items-baseline justify-between hover:bg-zinc-50 cursor-pointer px-2 transition-colors"
        >
          <span className="font-medium text-lg">Pending Tasks</span>
          <span className="text-6xl font-headline font-bold text-[#E6391E]">1</span>
        </div>

        <div
          onClick={onNavigateWorktrees}
          className="py-6 flex items-baseline justify-between hover:bg-zinc-50 cursor-pointer px-2 transition-colors"
        >
          <span className="font-medium text-lg">Active Worktrees</span>
          <span className="text-6xl font-headline font-bold text-[#0A0A0A]">1</span>
        </div>

        <div
          onClick={onNavigateDeployments}
          className="py-6 flex items-baseline justify-between hover:bg-zinc-50 cursor-pointer px-2 transition-colors"
        >
          <span className="font-medium text-lg">Vercel Status</span>
          <span className="font-mono text-lg font-bold text-[#E6391E]">LIVE ↗</span>
        </div>
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex items-center justify-between font-mono text-xs text-zinc-500">
        <span>DEV RUNTIME: NODE 22 + PY 3.12</span>
        <span className="text-[#0A0A0A] font-bold">ALPHABRAIN 2.0</span>
      </div>
    </div>
  );
};
