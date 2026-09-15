import React, { useState, useEffect } from 'react';
import { TaskDetail } from '../types';
import { mobileApi } from '../api/client';
import { ArrowLeft, GitBranch, FolderGit2, CheckCircle2, FileText, Code2 } from 'lucide-react';

interface Props {
  taskId: string;
  onBack: () => void;
  onViewDiff: (taskId: string) => void;
}

export const TaskDetailScreen: React.FC<Props> = ({ taskId, onBack, onViewDiff }) => {
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi.getTaskDetail(taskId).then((data) => {
      setTask(data);
      setLoading(false);
    });
  }, [taskId]);

  if (loading || !task) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Loading task details...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-card-border pb-3">
        <button onClick={onBack} className="flex items-center gap-1 text-muted hover:text-white font-mono text-xs">
          <ArrowLeft className="w-4 h-4" /> Back to Queue
        </button>
        <span className="font-mono text-xs text-accent">03 • SPEC REVIEW</span>
      </div>

      {/* Title & Metadata */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">{task.task_id}</span>
          <span className="font-mono text-xs bg-cyan-950 text-cyan-400 border border-cyan-800 px-2 py-0.5 rounded uppercase">
            {task.status}
          </span>
        </div>
        <h1 className="font-display text-xl font-bold text-white mt-2 leading-tight">{task.title}</h1>
      </div>

      {/* Worktree Containment Card */}
      <div className="locomotive-card p-4 rounded-lg space-y-2 text-xs font-mono">
        <div className="text-muted text-[10px] uppercase tracking-wider">GIT WORKTREE CONTAINMENT</div>
        <div className="flex items-center gap-2 text-slate-300">
          <GitBranch className="w-4 h-4 text-accent" />
          <span>Branch: {task.branch_name || `alpha/${task.task_id}`}</span>
        </div>
        <div className="flex items-center gap-2 text-slate-400 truncate">
          <FolderGit2 className="w-4 h-4 text-muted shrink-0" />
          <span className="truncate">{task.worktree_path}</span>
        </div>
      </div>

      {/* Acceptance Gates */}
      <div className="locomotive-card p-4 rounded-lg space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs text-muted">ACCEPTANCE GATES</span>
          <span className="font-mono text-[11px] text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" /> 2 OF 2 PASSED
          </span>
        </div>
        <div className="space-y-1.5 font-mono text-xs">
          {task.acceptance_commands.map((cmd, i) => (
            <div key={i} className="p-2 rounded bg-background border border-card-border flex items-center justify-between">
              <span className="text-slate-300 truncate pr-2">{cmd}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                PASS
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Checkpoints Stepper */}
      <div className="locomotive-card p-4 rounded-lg space-y-3">
        <span className="font-mono text-xs text-muted block">AUTONOMOUS LIFECYCLE CHECKPOINTS</span>
        <div className="space-y-2 font-mono text-xs">
          {task.checkpoints.map((cp, idx) => (
            <div key={idx} className="flex items-center justify-between py-1 border-b border-card-border/50">
              <div className="flex items-center gap-2">
                <span className="text-accent">{idx + 1}.</span>
                <span className="uppercase text-slate-200">{cp.step.replace('_', ' ')}</span>
              </div>
              <span className="text-[10px] uppercase text-emerald-400">{cp.status}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Action Footer */}
      <div className="pt-2">
        <button
          onClick={() => onViewDiff(task.task_id)}
          className="w-full py-3 rounded-lg bg-accent hover:bg-orange-600 text-white font-mono text-xs font-semibold flex items-center justify-center gap-2 transition-colors"
        >
          <Code2 className="w-4 h-4" /> Inspect Interactive Diff & Tests
        </button>
      </div>
    </div>
  );
};
