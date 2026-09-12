import React, { useState, useEffect } from 'react';
import { TaskSummary } from '../types';
import { mobileApi } from '../api/client';
import { CheckCircle2, XCircle, Clock, AlertTriangle, ShieldCheck, ArrowRight } from 'lucide-react';

interface Props {
  onSelectTask: (taskId: string) => void;
}

export const TriageQueueScreen: React.FC<Props> = ({ onSelectTask }) => {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadTasks = async () => {
    setLoading(true);
    try {
      const data = await mobileApi.listTriage(filter === 'all' ? undefined : filter);
      setTasks(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, [filter]);

  const handleReview = async (e: React.MouseEvent, taskId: string, action: 'approve' | 'reject') => {
    e.stopPropagation();
    setActionLoading(taskId);
    try {
      await mobileApi.reviewTask(taskId, action, `Mobile HITL ${action} from companion`);
      await loadTasks();
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">02 // HITL INTAKE</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Triage Queue</h1>
        </div>
        <span className="font-mono text-xs px-2 py-1 rounded bg-card border border-card-border text-muted">
          {tasks.length} TASKS
        </span>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1 font-mono text-xs">
        {['all', 'executing', 'pending_review', 'completed'].map((tab) => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            className={`px-3 py-1.5 rounded uppercase border whitespace-nowrap transition-colors ${
              filter === tab
                ? 'bg-accent/10 border-accent text-accent'
                : 'border-card-border text-muted hover:border-slate-600'
            }`}
          >
            {tab.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Task Rows */}
      {loading ? (
        <div className="p-8 text-center text-muted font-mono text-xs">Loading triage tasks...</div>
      ) : (
        <div className="space-y-3">
          {tasks.map((t, idx) => (
            <div
              key={t.task_id}
              onClick={() => onSelectTask(t.task_id)}
              className="locomotive-card p-4 rounded-lg cursor-pointer hover:border-accent transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-accent font-bold">0{idx + 1}</span>
                  <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    {t.task_id}
                  </span>
                  <span className="font-mono text-[10px] text-muted uppercase">[{t.category}]</span>
                </div>
                <span className={`font-mono text-[11px] px-2 py-0.5 rounded uppercase font-medium ${
                  t.status === 'executing'
                    ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                    : t.status === 'completed'
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    : 'bg-amber-950 text-amber-400 border border-amber-800'
                }`}>
                  {t.status}
                </span>
              </div>

              <div className="font-display text-sm font-semibold text-white group-hover:text-accent transition-colors mb-2">
                {t.title}
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-card-border text-xs">
                <div className="flex items-center gap-1.5 text-muted font-mono text-[11px]">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Risk: {t.risk_class}</span>
                </div>

                {t.status === 'executing' ? (
                  <div className="flex items-center gap-2">
                    <button
                      disabled={actionLoading === t.task_id}
                      onClick={(e) => handleReview(e, t.task_id, 'approve')}
                      className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-[11px] font-medium flex items-center gap-1"
                    >
                      <CheckCircle2 className="w-3 h-3" /> Approve
                    </button>
                    <button
                      disabled={actionLoading === t.task_id}
                      onClick={(e) => handleReview(e, t.task_id, 'reject')}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-red-400 font-mono text-[11px] font-medium flex items-center gap-1"
                    >
                      <XCircle className="w-3 h-3" /> Reject
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center text-muted group-hover:text-accent font-mono text-[11px]">
                    Inspect <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
