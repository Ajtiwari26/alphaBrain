import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';

interface Props {
  onMergeSuccess?: (branch: string) => void;
}

interface WorktreeItem {
  path: string;
  name: string;
  commit: string;
  branch: string;
}

export const WorktreesScreen: React.FC<Props> = ({ onMergeSuccess }) => {
  const [worktrees, setWorktrees] = useState<WorktreeItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi
      .getWorktrees()
      .then((data) => {
        setWorktrees(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          GIT INTEGRATION // ISOLATED WORKTREES
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Worktrees
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-4 overflow-y-auto max-h-[60vh]">
        {loading ? (
          <div className="p-8 text-center font-mono text-xs text-zinc-400">
            Querying active git worktrees...
          </div>
        ) : worktrees.length === 0 ? (
          <div className="p-8 text-center font-mono text-xs text-zinc-400">
            No external worktrees active. Main repo clean.
          </div>
        ) : (
          worktrees.map((wt) => {
            const isMain = wt.branch === 'main' || wt.name === 'alphaBrain';
            return (
              <div
                key={wt.path}
                className="py-4 px-1 flex items-center justify-between hover:bg-zinc-50 transition-colors"
              >
                <div className="flex-1 min-w-0 pr-3">
                  <span className="font-bold text-sm block truncate text-[#0A0A0A]">
                    {wt.branch || wt.name}
                  </span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="font-mono text-xs text-[#E6391E] font-semibold">
                      {wt.commit}
                    </span>
                    <span className="font-mono text-[10px] text-zinc-400 truncate">
                      {wt.name}
                    </span>
                  </div>
                </div>
                <span
                  className={`font-mono text-[10px] font-bold border px-2 py-0.5 whitespace-nowrap ${
                    isMain
                      ? 'border-[#0A0A0A] text-zinc-600 bg-zinc-100'
                      : 'border-[#E6391E] text-[#E6391E] bg-white'
                  }`}
                >
                  {isMain ? 'PROTECTED' : 'ISOLATED'}
                </span>
              </div>
            );
          })
        )}
      </div>

      <div className="border border-[#0A0A0A] p-4 bg-zinc-50">
        <div className="flex items-center justify-between font-mono text-xs">
          <span className="text-zinc-500">ACTIVE WORKTREES</span>
          <span className="font-bold text-[#0A0A0A]">{worktrees.length} DETECTED</span>
        </div>
      </div>
    </div>
  );
};
