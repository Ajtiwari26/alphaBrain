import React, { useState } from 'react';

interface Props {
  onMergeSuccess?: (branch: string) => void;
}

export const WorktreesScreen: React.FC<Props> = ({ onMergeSuccess }) => {
  const [merged, setMerged] = useState<Record<string, boolean>>({
    'feat/p14-mobile-companion': true,
  });

  const handleMerge = (branch: string) => {
    setMerged((prev) => ({ ...prev, [branch]: true }));
    onMergeSuccess?.(branch);
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          GIT INTEGRATION
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Worktrees
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-4">
        {/* Branch 1 */}
        <div className="py-5 px-1 flex items-center justify-between">
          <div>
            <span className="font-bold text-sm block">feat/p14-mobile-companion</span>
            <span className="font-mono text-xs text-[#E6391E] font-semibold">c9fe9c6</span>
          </div>
          <span className="font-mono text-xs text-zinc-500 font-bold border border-[#0A0A0A] px-2.5 py-1 bg-zinc-100">
            MERGED
          </span>
        </div>

        {/* Branch 2 */}
        <div className="py-5 px-1 flex items-center justify-between">
          <div>
            <span className="font-bold text-sm block">feat/splash-locomotive</span>
            <span className="font-mono text-xs text-[#E6391E] font-semibold">a1b2c3d</span>
          </div>
          {merged['feat/splash-locomotive'] ? (
            <span className="font-mono text-xs text-[#E6391E] font-bold">MERGED ✓</span>
          ) : (
            <button
              onClick={() => handleMerge('feat/splash-locomotive')}
              className="bg-[#0A0A0A] text-white px-3 py-1.5 font-mono text-xs font-bold hover:bg-[#E6391E] transition-colors"
            >
              MERGE
            </button>
          )}
        </div>

        {/* Branch 3 */}
        <div className="py-5 px-1 flex items-center justify-between">
          <div>
            <span className="font-bold text-sm block">main</span>
            <span className="font-mono text-xs text-zinc-400 font-semibold">360b501</span>
          </div>
          <span className="font-mono text-xs text-zinc-400 font-bold">PROTECTED</span>
        </div>
      </div>

      <div className="border border-[#0A0A0A] p-4 bg-zinc-50">
        <div className="flex items-center justify-between font-mono text-xs">
          <span className="text-zinc-500">FAST-FORWARD MERGE</span>
          <span className="font-bold text-[#0A0A0A]">ATOMIC // SAFE</span>
        </div>
      </div>
    </div>
  );
};
