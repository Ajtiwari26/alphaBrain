import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';
import { AuditLogEntry } from '../types';

export const LiveStreamScreen: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchLogs = () => {
    mobileApi
      .getAuditTrail(30)
      .then((data) => {
        setLogs(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(() => {
      if (!paused) {
        fetchLogs();
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [paused]);

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
          LIVE AUDIT LOG // CRYPTOGRAPHIC TRAIL
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Execution Log
        </h2>
      </div>

      <div className="flex-1 p-3 font-mono text-[11px] leading-relaxed overflow-y-auto max-h-[58vh] bg-zinc-50 border border-[#0A0A0A] my-4 space-y-2">
        {loading ? (
          <p className="text-zinc-400">Connecting to live AlphaBrain audit stream...</p>
        ) : logs.length === 0 ? (
          <p className="text-zinc-400">No recent audit events recorded.</p>
        ) : (
          logs.map((log) => {
            const timeStr = new Date(log.timestamp * 1000).toLocaleTimeString();
            const isFounder = log.actor === 'founder';
            const isEva = log.actor.includes('eva');

            return (
              <div key={log.event_id} className="border-b border-zinc-200 pb-1.5">
                <div className="flex items-center justify-between text-[10px] text-zinc-400">
                  <span>{timeStr}</span>
                  <span className="font-mono text-[9px] truncate max-w-[100px]">{log.sha256_hash.slice(0, 10)}</span>
                </div>
                <div className="mt-0.5">
                  <span
                    className={`font-bold ${
                      isFounder
                        ? 'text-[#E6391E]'
                        : isEva
                        ? 'text-[#0A0A0A]'
                        : 'text-zinc-600'
                    }`}
                  >
                    [{log.actor.toUpperCase()}]
                  </span>{' '}
                  <span className="text-[#0A0A0A] font-semibold">{log.action_type}</span>{' '}
                  <span className="text-zinc-500">→ {log.resource_id}</span>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex gap-3">
        <button
          onClick={() => setPaused(!paused)}
          className="flex-1 border border-[#0A0A0A] py-3 font-mono text-xs font-bold hover:bg-black hover:text-white transition-colors"
        >
          {paused ? 'RESUME STREAM' : 'PAUSE STREAM'}
        </button>
        <button
          onClick={fetchLogs}
          className="flex-1 bg-[#0A0A0A] text-white py-3 font-mono text-xs font-bold hover:bg-[#E6391E] transition-colors"
        >
          FORCE REFRESH
        </button>
      </div>
    </div>
  );
};
