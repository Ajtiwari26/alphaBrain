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

  const defaultTasks = [
    { task_id: 'TSK-042', title: 'Design Vector Logo', status: 'CODING' },
    { task_id: 'TSK-041', title: 'Opus Senior Review', status: 'IN REVIEW' },
    { task_id: 'TSK-040', title: 'Admit Founder Auth', status: 'QUEUED' },
  ];

  const displayTasks = tasks.length > 0 ? tasks : defaultTasks;

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          EXECUTION QUEUE
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Triage Board
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-4">
        {displayTasks.map((t) => {
          const isCoding = t.status.toLowerCase().includes('coding') || t.status.toLowerCase().includes('in_progress');
          const isReview = t.status.toLowerCase().includes('review') || t.status.toLowerCase().includes('debating');

          return (
            <div
              key={t.task_id}
              onClick={() => onSelectTask?.(t.task_id)}
              className="py-5 px-1 flex items-center justify-between hover:bg-zinc-50 cursor-pointer transition-colors group"
            >
              <div>
                <span className="font-mono text-xs text-zinc-400 block uppercase">
                  {t.task_id}
                </span>
                <span className="font-medium text-sm text-[#0A0A0A] mt-0.5 block">
                  {t.title}
                </span>
              </div>
              <span
                className={`font-mono text-xs font-bold uppercase ${
                  isCoding
                    ? 'text-[#E6391E]'
                    : isReview
                    ? 'text-zinc-600'
                    : 'text-zinc-400'
                }`}
              >
                {t.status}
              </span>
            </div>
          );
        })}
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex items-center justify-between font-mono text-xs">
        <span className="text-zinc-500">QUEUE TOTAL</span>
        <span className="font-bold text-[#0A0A0A]">{displayTasks.length} TASKS</span>
      </div>
    </div>
  );
};
