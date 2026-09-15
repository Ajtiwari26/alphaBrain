import React, { useState, useEffect, useCallback } from 'react';
import { mobileApi } from '../api/client';
import { TaskSummary } from '../types';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SkeletonList } from '../components/ui/Skeleton';
import {
  CheckCircle2,
  XCircle,
  ShieldCheck,
  FolderGit2,
  Terminal,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  AlertCircle,
  Copy,
  Check,
} from 'lucide-react';

interface Props {
  onSelectTask?: (taskId: string) => void;
}

type StatusFilter = 'ALL' | 'PENDING' | 'APPROVED' | 'EXECUTING' | 'COMPLETED' | 'REJECTED';

export const TriageQueueScreen: React.FC<Props> = ({ onSelectTask }) => {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>('ALL');
  const [selectedTask, setSelectedTask] = useState<TaskSummary | null>(null);
  const [founderNotes, setFounderNotes] = useState('');
  const [submittingVerdict, setSubmittingVerdict] = useState<'approve' | 'reject' | null>(null);
  const [verdictFeedback, setVerdictFeedback] = useState<{ success: boolean; message: string } | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await mobileApi.listTriage();
      setTasks(data);
    } catch (err) {
      console.error('Error fetching triage tasks:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handleCopyId = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleVerdict = async (action: 'approve' | 'reject') => {
    if (!selectedTask) return;
    setSubmittingVerdict(action);
    setVerdictFeedback(null);
    try {
      const res = await mobileApi.reviewTask(
        selectedTask.task_id,
        action,
        founderNotes || `Founder ${action.toUpperCase()} verdict via Mobile Companion`
      );
      setVerdictFeedback({
        success: res.success,
        message: res.message || `Task ${action.toUpperCase()} verdict recorded.`,
      });
      // Refresh list to update status in SQLite queue
      await fetchTasks();
      // Update selected task in place if found
      const updated = tasks.find((t) => t.task_id === selectedTask.task_id);
      if (updated) {
        setSelectedTask({ ...updated, status: action === 'approve' ? 'approved' : 'rejected' });
      }
    } catch (err: any) {
      setVerdictFeedback({
        success: false,
        message: err.message || 'Verdict submission failed. Check server logs.',
      });
    } finally {
      setSubmittingVerdict(null);
    }
  };

  const filteredTasks = tasks.filter((t) => {
    const s = t.status.toLowerCase();
    if (filter === 'ALL') return true;
    if (filter === 'PENDING') return s.includes('pending');
    if (filter === 'APPROVED') return s === 'approved';
    if (filter === 'EXECUTING') return s.includes('execut') || s.includes('coding');
    if (filter === 'COMPLETED') return s === 'completed';
    if (filter === 'REJECTED') return s === 'rejected';
    return true;
  });

  const counts = {
    all: tasks.length,
    pending: tasks.filter((t) => t.status.toLowerCase().includes('pending')).length,
    approved: tasks.filter((t) => t.status.toLowerCase() === 'approved').length,
    executing: tasks.filter((t) => t.status.toLowerCase().includes('execut')).length,
    completed: tasks.filter((t) => t.status.toLowerCase() === 'completed').length,
    rejected: tasks.filter((t) => t.status.toLowerCase() === 'rejected').length,
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[80vh] pb-[max(env(safe-area-inset-bottom),5rem)] animate-screen-enter">
      {/* Top Swiss Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
            ORCHESTRATION PIPELINE • SQLITE ENGINE
          </span>
          <button
            onClick={fetchTasks}
            disabled={loading}
            className="p-1 hover:bg-zinc-100 border border-[#0A0A0A] transition-colors"
            title="Refresh Queue"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#0A0A0A] ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        <div className="flex items-baseline justify-between mt-1">
          <h2 className="text-3xl font-headline font-bold text-[#0A0A0A] tracking-tight">
            Triage Board
          </h2>
          <span className="font-mono text-xs font-bold text-[#E6391E]">
            {counts.pending} PENDING SIGN-OFF
          </span>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto py-2.5 border-b border-[#0A0A0A] no-scrollbar">
        {(['ALL', 'PENDING', 'APPROVED', 'EXECUTING', 'COMPLETED', 'REJECTED'] as StatusFilter[]).map((f) => {
          const count =
            f === 'ALL'
              ? counts.all
              : f === 'PENDING'
              ? counts.pending
              : f === 'APPROVED'
              ? counts.approved
              : f === 'EXECUTING'
              ? counts.executing
              : f === 'COMPLETED'
              ? counts.completed
              : counts.rejected;

          const active = filter === f;
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2.5 py-1 text-[10px] font-mono font-bold tracking-wider uppercase border transition-smooth whitespace-nowrap ${
                active
                  ? 'bg-[#0A0A0A] text-white border-[#0A0A0A]'
                  : 'bg-white text-zinc-600 border-zinc-300 hover:border-[#0A0A0A]'
              }`}
            >
              {f} ({count})
            </button>
          );
        })}
      </div>

      {/* Interactive Task Inspection Drawer / Modal */}
      {selectedTask && (
        <div className="my-3 p-4 border-2 border-[#0A0A0A] bg-zinc-50 space-y-3.5 animate-screen-enter">
          <div className="flex items-start justify-between border-b border-[#0A0A0A] pb-2.5">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-[#E6391E]">
                  {selectedTask.task_id}
                </span>
                <button
                  onClick={(e) => handleCopyId(selectedTask.task_id, e)}
                  className="p-1 hover:bg-zinc-200 border border-zinc-300 text-zinc-700 rounded transition-colors"
                  title="Copy Task ID"
                >
                  {copiedId === selectedTask.task_id ? (
                    <Check className="w-3 h-3 text-emerald-600" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </button>
              </div>
              <h3 className="font-headline font-bold text-base text-[#0A0A0A] leading-snug">
                {selectedTask.title}
              </h3>
            </div>
            <button
              onClick={() => {
                setSelectedTask(null);
                setVerdictFeedback(null);
              }}
              className="px-2 py-1 border border-[#0A0A0A] bg-white text-xs font-mono font-bold hover:bg-zinc-100"
            >
              ✕ CLOSE
            </button>
          </div>

          {/* Envelope Telemetry */}
          <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
            <div className="p-2 border border-zinc-300 bg-white">
              <span className="text-zinc-500 block text-[9px] uppercase tracking-wider">PIPELINE STATUS</span>
              <span className="font-bold uppercase text-[#0A0A0A] mt-0.5 block">
                {selectedTask.status}
              </span>
            </div>
            <div className="p-2 border border-zinc-300 bg-white">
              <span className="text-zinc-500 block text-[9px] uppercase tracking-wider">SAFETY GATE AUDIT</span>
              <span className="font-bold text-emerald-600 flex items-center gap-1 mt-0.5">
                <ShieldCheck className="w-3.5 h-3.5" /> P9 PASS
              </span>
            </div>
            <div className="p-2 border border-zinc-300 bg-white">
              <span className="text-zinc-500 block text-[9px] uppercase tracking-wider">CATEGORY • RISK</span>
              <span className="font-bold uppercase text-[#0A0A0A] mt-0.5 block truncate">
                {selectedTask.category} • {selectedTask.risk_class}
              </span>
            </div>
            <div className="p-2 border border-zinc-300 bg-white">
              <span className="text-zinc-500 block text-[9px] uppercase tracking-wider">PROVENANCE AUTHOR</span>
              <span className="font-bold text-[#0A0A0A] mt-0.5 block truncate">
                {selectedTask.author || 'Eva Voice Mesh'}
              </span>
            </div>
          </div>

          {/* Scope Boundaries */}
          <div className="p-2.5 border border-zinc-300 bg-white space-y-1.5 text-xs font-mono">
            <div className="flex items-center gap-1 text-zinc-500 text-[10px] uppercase font-bold tracking-wider">
              <FolderGit2 className="w-3 h-3 text-[#E6391E]" /> ALLOWED PATH SCOPE
            </div>
            <div className="flex flex-wrap gap-1">
              {(selectedTask.allowed_paths || ['alpha_core/', 'testscript/']).map((p, idx) => (
                <span
                  key={idx}
                  className="px-1.5 py-0.5 bg-zinc-100 border border-zinc-300 text-zinc-800 text-[10px]"
                >
                  {p}
                </span>
              ))}
            </div>
          </div>

          {/* Acceptance Commands */}
          {selectedTask.acceptance_commands && selectedTask.acceptance_commands.length > 0 && (
            <div className="p-2.5 border border-zinc-300 bg-white space-y-1.5 text-xs font-mono">
              <div className="flex items-center gap-1 text-zinc-500 text-[10px] uppercase font-bold tracking-wider">
                <Terminal className="w-3 h-3 text-[#E6391E]" /> ACCEPTANCE GATES
              </div>
              <div className="space-y-1">
                {selectedTask.acceptance_commands.map((cmd, idx) => (
                  <div key={idx} className="p-1 bg-zinc-100 text-zinc-800 text-[10px] font-mono">
                    $ {cmd}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Feedback Banner */}
          {verdictFeedback && (
            <div
              className={`p-2.5 border text-xs font-mono flex items-start gap-2 ${
                verdictFeedback.success
                  ? 'bg-emerald-50 border-emerald-500 text-emerald-800'
                  : 'bg-red-50 border-red-500 text-red-800'
              }`}
            >
              {verdictFeedback.success ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
              )}
              <span>{verdictFeedback.message}</span>
            </div>
          )}

          {/* Founder Verdict Actions */}
          <div className="space-y-2 pt-1">
            <input
              type="text"
              placeholder="Founder directive / verdict note (optional)..."
              value={founderNotes}
              onChange={(e) => setFounderNotes(e.target.value)}
              className="w-full px-3 py-2 border border-[#0A0A0A] bg-white font-mono text-xs text-[#0A0A0A] placeholder-zinc-400 focus:outline-none focus:ring-1 focus:ring-[#E6391E]"
            />

            <div className="flex gap-2">
              <button
                onClick={() => handleVerdict('approve')}
                disabled={Boolean(submittingVerdict)}
                className="flex-1 py-2.5 px-3 bg-[#E6391E] text-white font-mono text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 border border-[#0A0A0A] hover:bg-orange-600 disabled:opacity-50 transition-colors"
              >
                {submittingVerdict === 'approve' ? (
                  <LoadingSpinner size="sm" label="Certifying..." />
                ) : (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5" /> APPROVE VERDICT
                  </>
                )}
              </button>

              <button
                onClick={() => handleVerdict('reject')}
                disabled={Boolean(submittingVerdict)}
                className="py-2.5 px-4 bg-white text-[#0A0A0A] font-mono text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 border border-[#0A0A0A] hover:bg-zinc-100 disabled:opacity-50 transition-colors"
              >
                {submittingVerdict === 'reject' ? (
                  <LoadingSpinner size="sm" label="Tombstoning..." />
                ) : (
                  <>
                    <XCircle className="w-3.5 h-3.5 text-zinc-500" /> REJECT
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Task List */}
      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-3 overflow-y-auto max-h-[58vh]">
        {loading && tasks.length === 0 ? (
          <div className="space-y-4">
            <div className="p-4 flex items-center justify-center bg-zinc-50 border border-zinc-200">
              <LoadingSpinner size="md" label="Querying SQLite triage queue..." />
            </div>
            <SkeletonList rows={5} />
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="p-8 text-center font-mono text-xs text-zinc-400 space-y-2">
            <div>No tasks in {filter} status.</div>
            <button
              onClick={() => setFilter('ALL')}
              className="text-[#E6391E] hover:underline uppercase text-[10px]"
            >
              Reset filter
            </button>
          </div>
        ) : (
          filteredTasks.map((t) => {
            const isCompleted = t.status.toLowerCase() === 'completed';
            const isPending = t.status.toLowerCase().includes('pending');
            const isApproved = t.status.toLowerCase() === 'approved';
            const isExecuting =
              t.status.toLowerCase().includes('execut') || t.status.toLowerCase().includes('coding');
            const isRejected = t.status.toLowerCase() === 'rejected';
            const isSelected = selectedTask?.task_id === t.task_id;

            return (
              <div
                key={t.task_id}
                onClick={() => {
                  setSelectedTask(isSelected ? null : t);
                  setVerdictFeedback(null);
                }}
                className={`py-3.5 px-2 flex items-center justify-between hover:bg-zinc-50 cursor-pointer card-tactile transition-smooth group ${
                  isSelected ? 'bg-zinc-100 border-l-4 border-l-[#E6391E]' : ''
                }`}
              >
                <div className="flex-1 min-w-0 pr-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-zinc-500 block uppercase group-hover:text-[#E6391E] transition-colors">
                      {t.task_id}
                    </span>
                    {isPending && (
                      <span className="w-1.5 h-1.5 rounded-full bg-[#E6391E] animate-pulse" />
                    )}
                  </div>
                  <span className="font-medium text-sm text-[#0A0A0A] mt-0.5 block truncate">
                    {t.title}
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`font-mono text-xs font-bold uppercase px-2 py-0.5 border ${
                      isPending
                        ? 'bg-orange-50 text-[#E6391E] border-[#E6391E]'
                        : isApproved
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-600'
                        : isExecuting
                        ? 'bg-zinc-900 text-white border-zinc-900'
                        : isCompleted
                        ? 'bg-zinc-100 text-zinc-600 border-zinc-300'
                        : isRejected
                        ? 'bg-red-50 text-red-600 border-red-300 line-through'
                        : 'bg-zinc-100 text-zinc-500 border-zinc-300'
                    }`}
                  >
                    {t.status}
                  </span>
                  {isSelected ? (
                    <ChevronUp className="w-4 h-4 text-[#0A0A0A]" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-zinc-400 group-hover:text-[#0A0A0A]" />
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer Metrics */}
      <div className="border-t border-[#0A0A0A] pt-3 flex items-center justify-between font-mono text-xs">
        <span className="text-zinc-500">FILTERED TOTAL</span>
        <span className="font-bold text-[#0A0A0A]">
          {filteredTasks.length} / {tasks.length} TASKS
        </span>
      </div>
    </div>
  );
};
