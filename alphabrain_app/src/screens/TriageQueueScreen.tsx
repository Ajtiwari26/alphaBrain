import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';
import { TaskSummary } from '../types';

interface Props {
  onSelectTask?: (taskId: string) => void;
}

export const TriageQueueScreen: React.FC<Props> = ({ onSelectTask }) => {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi
      .listTriage()
      .then((data) => {
        setTasks(data);
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
          EXECUTION QUEUE // SQLITE TRIAGE ENGINE
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Triage Board
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-4 overflow-y-auto max-h-[60vh]">
        {loading ? (
          <div className="p-8 text-center font-mono text-xs text-zinc-400">
            Querying SQLite triage queue...
          </div>
        ) : tasks.length === 0 ? (
          <div className="p-8 text-center font-mono text-xs text-zinc-400">
            Queue empty. No pending tasks.
          </div>
        ) : (
          tasks.map((t) => {
            const isCompleted = t.status.toLowerCase() === 'completed';
            const isPending = t.status.toLowerCase().includes('pending');
            const isExecuting = t.status.toLowerCase().includes('execut') || t.status.toLowerCase().includes('coding');

            return (
              <div
                key={t.task_id}
                onClick={() => onSelectTask?.(t.task_id)}
                className="py-4 px-1 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors group"
              >
                <div className="flex-1 min-w-0 pr-3">
                  <span className="font-mono text-xs text-zinc-400 block uppercase">
                    {t.task_id}
                  </span>
                  <span className="font-medium text-sm text-[#0A0A0A] mt-0.5 block truncate">
                    {t.title}
                  </span>
                </div>
                <span
                  className={`font-mono text-xs font-bold uppercase whitespace-nowrap ${
                    isPending
                      ? 'text-[#E6391E]'
                      : isExecuting
                      ? 'text-zinc-900 font-extrabold'
                      : isCompleted
                      ? 'text-zinc-500'
                      : 'text-zinc-400'
                  }`}
                >
                  {t.status}
                </span>
              </div>
            );
          })
        )}
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex items-center justify-between font-mono text-xs">
        <span className="text-zinc-500">QUEUE TOTAL</span>
        <span className="font-bold text-[#0A0A0A]">{tasks.length} TASKS</span>
      </div>
    </div>
  );
};
