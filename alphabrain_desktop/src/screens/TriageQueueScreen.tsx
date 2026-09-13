import React, { useState, useEffect, useRef } from 'react';
import { desktopApi } from '../api/client';
import { TaskSummary } from '../types';
import { RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';

interface Props {
  onSelectTask?: (taskId: string) => void;
}

export const TriageQueueScreen: React.FC<Props> = ({ onSelectTask }) => {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const feedbackTimerRef = useRef<number | null>(null);

  const fetchTasks = () => {
    setLoading(true);
    desktopApi
      .listTriage()
      .then((data) => {
        setTasks(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load triage tasks:', err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchTasks();
    return () => {
      if (feedbackTimerRef.current !== null) {
        clearTimeout(feedbackTimerRef.current);
      }
    };
  }, []);

  const handleReview = async (taskId: string, action: 'approve' | 'reject') => {
    setReviewingId(taskId);
    try {
      await desktopApi.reviewTask(
        taskId,
        action,
        action === 'approve'
          ? 'Approved by Founder Ajay from Mac Command Node'
          : 'Rejected by Founder Ajay'
      );
      setFeedback({ type: 'success', message: `Task ${taskId} successfully ${action}d.` });
      fetchTasks();
    } catch (err) {
      console.error(`Failed to ${action} task:`, err);
      setFeedback({
        type: 'error',
        message: `Failed to ${action} task ${taskId}. Backend service unreachable.`,
      });
    } finally {
      setReviewingId(null);
      if (feedbackTimerRef.current !== null) {
        clearTimeout(feedbackTimerRef.current);
      }
      feedbackTimerRef.current = window.setTimeout(() => {
        setFeedback(null);
        feedbackTimerRef.current = null;
      }, 5000);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-6">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#E6391E] font-bold uppercase tracking-widest">
              EXECUTION QUEUE // SQLITE TRIAGE ENGINE
            </span>
            <span className="text-neutral-300">•</span>
            <span className="font-mono text-xs text-neutral-500 uppercase">
              FOUNDER GOVERNANCE GATE
            </span>
          </div>
          <h1 className="text-3xl font-bold font-sans tracking-tight mt-1 text-[#0A0A0A]">
            Triage & Execution Queue
          </h1>
          <p className="font-mono text-xs text-neutral-500 mt-1">
            Deterministic SafetyGate evaluation, founder approval gate, and autonomous worker dispatch
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchTasks}
            className="flex items-center gap-2 px-4 py-2 border border-[#0A0A0A] bg-white font-mono text-xs font-bold hover:bg-neutral-100 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#E6391E]' : ''}`} />
            <span>REFRESH QUEUE</span>
          </button>
        </div>
      </div>

      {feedback && (
        <div
          className={`p-3 border border-[#0A0A0A] font-mono text-xs flex items-center gap-2 ${
            feedback.type === 'success'
              ? 'bg-emerald-50 text-emerald-800'
              : 'bg-red-50 text-red-800'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-[#E6391E] shrink-0" />
          )}
          <span>{feedback.message}</span>
        </div>
      )}


      {/* Task List Table */}
      <div className="border border-[#0A0A0A] bg-white">
        <div className="grid grid-cols-12 px-6 py-3 border-b border-[#0A0A0A] bg-neutral-50 font-mono text-xs text-neutral-500 font-bold uppercase">
          <div className="col-span-3">Task ID & Category</div>
          <div className="col-span-4">Directive Title</div>
          <div className="col-span-1 text-center">Priority</div>
          <div className="col-span-2 text-center">Status</div>
          <div className="col-span-2 text-right">Founder Action</div>
        </div>

        {loading ? (
          <div className="p-12 text-center font-mono text-xs text-neutral-400">
            Querying SQLite triage queue...
          </div>
        ) : tasks.length === 0 ? (
          <div className="p-12 text-center font-mono text-xs text-neutral-400">
            Queue is empty. No pending tasks.
          </div>
        ) : (
          <div className="divide-y divide-neutral-200">
            {tasks.map((t) => {
              const isExecuting = t.status.toLowerCase().includes('execut') || t.status.toLowerCase().includes('coding');
              const isPending = t.status.toLowerCase().includes('pending');
              const isApproved = t.status.toLowerCase().includes('approved') || t.status.toLowerCase().includes('ready');

              return (
                <div
                  key={t.task_id}
                  className="grid grid-cols-12 px-6 py-4 items-center hover:bg-neutral-50 transition-colors"
                >
                  <div className="col-span-3 pr-4">
                    <span
                      onClick={() => onSelectTask?.(t.task_id)}
                      className="font-mono text-xs font-bold text-[#E6391E] block cursor-pointer hover:underline"
                    >
                      {t.task_id}
                    </span>
                    <span className="font-mono text-[10px] text-neutral-400 uppercase">
                      {t.category || 'GENERAL'} // {t.risk_class || 'LOW'} RISK
                    </span>
                  </div>

                  <div className="col-span-4 pr-4">
                    <p className="font-medium text-sm text-[#0A0A0A] leading-snug line-clamp-2">
                      {t.title}
                    </p>
                    <span className="font-mono text-[10px] text-neutral-400">
                      BY: {t.author || 'FOUNDER'}
                    </span>
                  </div>

                  <div className="col-span-1 text-center font-mono text-xs font-bold">
                    <span className="bg-neutral-100 border border-neutral-300 px-2 py-0.5">
                      {t.priority || 'P1'}
                    </span>
                  </div>

                  <div className="col-span-2 text-center">
                    <span
                      className={`font-mono text-[11px] font-bold uppercase px-2.5 py-1 inline-block border ${
                        isExecuting
                          ? 'bg-[#0A0A0A] text-white border-[#0A0A0A]'
                          : isPending
                          ? 'bg-amber-50 text-amber-800 border-amber-300'
                          : isApproved
                          ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                          : 'bg-neutral-100 text-neutral-700 border-neutral-300'
                      }`}
                    >
                      {t.status}
                    </span>
                  </div>

                  <div className="col-span-2 flex items-center justify-end gap-2">
                    {isPending ? (
                      <>
                        <button
                          disabled={reviewingId === t.task_id}
                          onClick={() => handleReview(t.task_id, 'approve')}
                          className="px-3 py-1.5 border border-[#0A0A0A] bg-emerald-600 hover:bg-emerald-700 text-white font-mono text-[11px] font-bold transition-all"
                        >
                          APPROVE
                        </button>
                        <button
                          disabled={reviewingId === t.task_id}
                          onClick={() => handleReview(t.task_id, 'reject')}
                          className="px-3 py-1.5 border border-[#0A0A0A] bg-white hover:bg-neutral-100 text-[#0A0A0A] font-mono text-[11px] font-bold transition-all"
                        >
                          REJECT
                        </button>
                      </>
                    ) : isExecuting ? (
                      <span className="font-mono text-[11px] text-[#E6391E] font-bold flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-ping" />
                        RUNNING
                      </span>
                    ) : (
                      <span className="font-mono text-[11px] text-neutral-400">
                        RESOLVED
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer statistics summary */}
      <div className="border border-[#0A0A0A] bg-neutral-50 p-4 font-mono text-xs flex justify-between items-center">
        <span className="text-neutral-500">TRIAGE BACKLOG</span>
        <span className="font-bold text-[#0A0A0A]">
          {tasks.length} TASKS IN QUEUE
        </span>
      </div>
    </div>
  );
};
