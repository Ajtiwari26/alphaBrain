import React, { useState, useEffect, useMemo } from 'react';
import { mobileApi } from '../api/client';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SkeletonList } from '../components/ui/Skeleton';
import {
  GitBranch,
  Search,
  RefreshCw,
  ShieldCheck,
  Cpu,
  Layers,
  ExternalLink,
  Copy,
  Check,
  X,
  ChevronRight,
  FolderGit2,
  Terminal,
} from 'lucide-react';

interface Props {
  onMergeSuccess?: (branch: string) => void;
  onNavigateToTask?: (taskId: string) => void;
}

interface WorktreeItem {
  path: string;
  name: string;
  commit: string;
  branch: string;
}

export const WorktreesScreen: React.FC<Props> = ({ onMergeSuccess, onNavigateToTask }) => {
  const [worktrees, setWorktrees] = useState<WorktreeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'tasks' | 'proof' | 'protected'>('all');
  const [selectedWorktree, setSelectedWorktree] = useState<WorktreeItem | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const fetchWorktrees = async () => {
    try {
      const data = await mobileApi.getWorktrees();
      setWorktrees(data);
    } catch (err) {
      console.error('Failed to fetch worktrees:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchWorktrees();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchWorktrees();
  };

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Helper to extract Task ID if worktree is tied to a task
  const extractTaskId = (branchOrName: string): string | null => {
    const match = branchOrName.match(/(tsk_[a-zA-Z0-9_]+)/i);
    return match ? match[1].toUpperCase() : null;
  };

  // Filtered list
  const filteredWorktrees = useMemo(() => {
    return worktrees.filter((wt) => {
      const branch = (wt.branch || '').toLowerCase();
      const name = (wt.name || '').toLowerCase();
      const commit = (wt.commit || '').toLowerCase();
      const q = searchQuery.toLowerCase();

      const matchesSearch =
        !q ||
        branch.includes(q) ||
        name.includes(q) ||
        commit.includes(q) ||
        wt.path.toLowerCase().includes(q);

      if (!matchesSearch) return false;

      const isMain = wt.branch === 'main' || wt.name === 'alphaBrain';
      const isProof = branch.includes('proof') || name.includes('proof');
      const isTask =
        Boolean(extractTaskId(branch) || extractTaskId(name)) ||
        branch.includes('tsk_') ||
        name.includes('tsk_');

      if (activeFilter === 'protected') return isMain;
      if (activeFilter === 'proof') return isProof;
      if (activeFilter === 'tasks') return isTask;
      return true;
    });
  }, [worktrees, searchQuery, activeFilter]);

  const taskWorktreeCount = useMemo(() => {
    return worktrees.filter(
      (wt) =>
        (wt.branch || '').includes('tsk_') ||
        (wt.name || '').includes('tsk_') ||
        (wt.branch || '').includes('h5a')
    ).length;
  }, [worktrees]);

  const proofCount = useMemo(() => {
    return worktrees.filter(
      (wt) =>
        (wt.branch || '').includes('proof') ||
        (wt.name || '').includes('proof')
    ).length;
  }, [worktrees]);

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh] animate-screen-enter pb-16">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase flex items-center gap-1.5">
            <GitBranch className="w-3 h-3 text-[#E6391E]" />
            GIT ARCHITECTURE • WORKTREE RADAR
          </span>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1 text-[11px] font-mono font-bold text-zinc-600 hover:text-black transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin text-[#E6391E]' : ''}`} />
            <span>SYNC</span>
          </button>
        </div>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Worktrees
        </h2>
        <p className="font-sans text-xs text-zinc-500 mt-0.5">
          Isolated file-system checkouts for autonomous AGY coding workers. Zero branch collisions on main.
        </p>
      </div>

      {/* Metrics Banner */}
      <div className="grid grid-cols-3 gap-2 my-3">
        <div className="border border-[#0A0A0A] p-2.5 bg-zinc-50 flex flex-col">
          <span className="font-mono text-[9px] text-zinc-500 uppercase">ACTIVE TOTAL</span>
          <span className="font-mono text-lg font-black text-[#0A0A0A] mt-0.5">
            {loading ? '...' : worktrees.length}
          </span>
          <span className="font-mono text-[9px] text-zinc-400">git instances</span>
        </div>

        <div className="border border-[#0A0A0A] p-2.5 bg-zinc-50 flex flex-col">
          <span className="font-mono text-[9px] text-zinc-500 uppercase">TASK WORKERS</span>
          <span className="font-mono text-lg font-black text-[#E6391E] mt-0.5">
            {loading ? '...' : taskWorktreeCount}
          </span>
          <span className="font-mono text-[9px] text-zinc-400">sandboxed tasks</span>
        </div>

        <div className="border border-[#0A0A0A] p-2.5 bg-zinc-50 flex flex-col">
          <span className="font-mono text-[9px] text-zinc-500 uppercase">PROOF RUNS</span>
          <span className="font-mono text-lg font-black text-blue-600 mt-0.5">
            {loading ? '...' : proofCount}
          </span>
          <span className="font-mono text-[9px] text-zinc-400">verification</span>
        </div>
      </div>

      {/* Search & Filter Controls */}
      <div className="space-y-2 mb-3">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder="Search branch, task ID, commit SHA..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs font-mono bg-zinc-50 border border-[#0A0A0A] placeholder:text-zinc-400 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[#0A0A0A]"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-black"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px] font-mono scrollbar-none">
          <button
            onClick={() => setActiveFilter('all')}
            className={`px-2.5 py-1 border whitespace-nowrap font-bold transition-colors ${
              activeFilter === 'all'
                ? 'bg-[#0A0A0A] text-white border-[#0A0A0A]'
                : 'bg-white text-zinc-600 border-zinc-300 hover:border-black'
            }`}
          >
            ALL ({worktrees.length})
          </button>
          <button
            onClick={() => setActiveFilter('tasks')}
            className={`px-2.5 py-1 border whitespace-nowrap font-bold transition-colors ${
              activeFilter === 'tasks'
                ? 'bg-[#E6391E] text-white border-[#E6391E]'
                : 'bg-white text-zinc-600 border-zinc-300 hover:border-[#E6391E]'
            }`}
          >
            TASKS ({taskWorktreeCount})
          </button>
          <button
            onClick={() => setActiveFilter('proof')}
            className={`px-2.5 py-1 border whitespace-nowrap font-bold transition-colors ${
              activeFilter === 'proof'
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-zinc-600 border-zinc-300 hover:border-blue-600'
            }`}
          >
            PROOFS ({proofCount})
          </button>
          <button
            onClick={() => setActiveFilter('protected')}
            className={`px-2.5 py-1 border whitespace-nowrap font-bold transition-colors ${
              activeFilter === 'protected'
                ? 'bg-zinc-800 text-white border-zinc-800'
                : 'bg-white text-zinc-600 border-zinc-300 hover:border-black'
            }`}
          >
            PROTECTED (1)
          </button>
        </div>
      </div>

      {/* Worktrees List */}
      <div className="flex-1 flex flex-col divide-y divide-zinc-200 overflow-y-auto max-h-[50vh] border border-[#0A0A0A] bg-zinc-50/50">
        {loading ? (
          <div className="p-4 space-y-3">
            <div className="p-4 flex items-center justify-center bg-white border border-zinc-200">
              <LoadingSpinner size="md" label="Querying git worktree porcelain..." />
            </div>
            <SkeletonList rows={5} />
          </div>
        ) : filteredWorktrees.length === 0 ? (
          <div className="p-8 text-center font-mono text-xs text-zinc-400 space-y-1">
            <FolderGit2 className="w-8 h-8 text-zinc-300 mx-auto mb-2" />
            <p className="font-bold text-zinc-600">No matching worktrees found</p>
            <p className="text-[10px]">Try clearing your search query or filter pills.</p>
          </div>
        ) : (
          filteredWorktrees.map((wt) => {
            const isMain = wt.branch === 'main' || wt.name === 'alphaBrain';
            const taskId = extractTaskId(wt.branch) || extractTaskId(wt.name);
            const isProof = (wt.branch || '').includes('proof');

            return (
              <div
                key={wt.path}
                onClick={() => setSelectedWorktree(wt)}
                className="p-3 bg-white hover:bg-zinc-50 card-tactile transition-smooth cursor-pointer flex flex-col gap-1.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-mono text-xs font-bold text-[#0A0A0A] truncate">
                        {wt.branch || wt.name}
                      </span>
                      {isMain && (
                        <span className="inline-flex items-center gap-1 font-mono text-[9px] font-black border border-black bg-black text-white px-1.5 py-0.5">
                          <ShieldCheck className="w-2.5 h-2.5" />
                          MAIN REPO
                        </span>
                      )}
                      {taskId && (
                        <span className="font-mono text-[9px] font-bold border border-[#E6391E] bg-red-50 text-[#E6391E] px-1.5 py-0.5">
                          TASK: {taskId}
                        </span>
                      )}
                      {isProof && !taskId && (
                        <span className="font-mono text-[9px] font-bold border border-blue-500 bg-blue-50 text-blue-600 px-1.5 py-0.5">
                          PROOF VERIFY
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 mt-1">
                      <span className="font-mono text-[11px] font-semibold text-[#E6391E] bg-zinc-100 px-1.5 py-0.5 border border-zinc-200">
                        {wt.commit}
                      </span>
                      <span className="font-mono text-[10px] text-zinc-400 truncate max-w-[200px]">
                        {wt.path.replace('/Users/ajaytiwari', '~')}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 text-zinc-400 self-center">
                    <ChevronRight className="w-4 h-4" />
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer Info */}
      <div className="border border-[#0A0A0A] p-3 bg-zinc-50 mt-3 flex items-center justify-between font-mono text-[11px]">
        <div className="flex items-center gap-1.5 text-zinc-600">
          <Cpu className="w-3.5 h-3.5 text-[#E6391E]" />
          <span>INVARIANT I-5: ZERO DIRECT MAIN EDITS</span>
        </div>
        <span className="font-bold text-[#0A0A0A]">
          {filteredWorktrees.length} OF {worktrees.length} SHOWN
        </span>
      </div>

      {/* Interactive Detail Modal Drawer */}
      {selectedWorktree && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-white border-t-2 sm:border-2 border-[#0A0A0A] w-full max-w-md p-5 space-y-4 shadow-2xl animate-screen-enter max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-3">
              <div className="flex items-center gap-2">
                <FolderGit2 className="w-4 h-4 text-[#E6391E]" />
                <span className="font-mono text-xs font-bold uppercase tracking-wider">
                  WORKTREE INSPECTION
                </span>
              </div>
              <button
                onClick={() => setSelectedWorktree(null)}
                className="w-7 h-7 border border-[#0A0A0A] flex items-center justify-center hover:bg-black hover:text-white transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div>
                <span className="text-[10px] text-zinc-500 uppercase block">BRANCH</span>
                <div className="font-bold text-sm text-[#0A0A0A] flex items-center justify-between mt-0.5">
                  <span className="truncate">{selectedWorktree.branch || selectedWorktree.name}</span>
                  <button
                    onClick={() =>
                      copyToClipboard(selectedWorktree.branch || selectedWorktree.name, 'branch')
                    }
                    className="text-zinc-400 hover:text-black text-[10px] flex items-center gap-1 ml-2"
                  >
                    {copiedField === 'branch' ? (
                      <Check className="w-3 h-3 text-emerald-600" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
              </div>

              <div>
                <span className="text-[10px] text-zinc-500 uppercase block">HEAD COMMIT SHA</span>
                <div className="font-bold text-sm text-[#E6391E] flex items-center justify-between mt-0.5">
                  <span>{selectedWorktree.commit}</span>
                  <button
                    onClick={() => copyToClipboard(selectedWorktree.commit, 'commit')}
                    className="text-zinc-400 hover:text-black text-[10px] flex items-center gap-1 ml-2"
                  >
                    {copiedField === 'commit' ? (
                      <Check className="w-3 h-3 text-emerald-600" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
              </div>

              <div>
                <span className="text-[10px] text-zinc-500 uppercase block">LOCAL FILESYSTEM PATH</span>
                <div className="p-2 bg-zinc-100 border border-zinc-200 text-[10px] break-all select-all flex items-start justify-between gap-2 mt-0.5">
                  <span>{selectedWorktree.path}</span>
                  <button
                    onClick={() => copyToClipboard(selectedWorktree.path, 'path')}
                    className="text-zinc-500 hover:text-black shrink-0 mt-0.5"
                  >
                    {copiedField === 'path' ? (
                      <Check className="w-3 h-3 text-emerald-600" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
              </div>

              {extractTaskId(selectedWorktree.branch || selectedWorktree.name) && (
                <div className="p-3 border border-[#E6391E] bg-red-50 space-y-1">
                  <span className="text-[10px] font-bold text-[#E6391E] uppercase flex items-center gap-1">
                    <Terminal className="w-3 h-3" />
                    BOUND TO AUTONOMOUS TASK
                  </span>
                  <p className="text-xs font-bold text-[#0A0A0A]">
                    {extractTaskId(selectedWorktree.branch || selectedWorktree.name)}
                  </p>
                  <p className="text-[10px] text-zinc-600 font-sans">
                    This worktree is currently or previously leased to an AGY coding agent cycle. Changes are isolated from the main repository.
                  </p>
                </div>
              )}

              <div className="p-3 border border-zinc-300 bg-zinc-50 space-y-1">
                <span className="text-[10px] font-bold text-zinc-700 uppercase">
                  BRANCH ISOLATION GUARANTEE
                </span>
                <p className="text-[11px] font-sans text-zinc-600">
                  Worker agent processes and test scripts execute strictly inside this directory path. Git index locks and stashes are encapsulated within this isolated tree.
                </p>
              </div>
            </div>

            <div className="border-t border-zinc-200 pt-3 flex gap-2">
              <button
                onClick={() => setSelectedWorktree(null)}
                className="flex-1 py-2.5 bg-[#0A0A0A] text-white font-mono text-xs font-bold hover:bg-[#E6391E] transition-colors"
              >
                CLOSE INSPECTION
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
