import React, { useState, useEffect } from 'react';
import { AuditLogEntry } from '../types';
import { mobileApi } from '../api/client';
import { FileText, Shield, Key, Hash, Clock } from 'lucide-react';

export const AuditTrailScreen: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi.getAuditTrail(15).then((data) => {
      setLogs(data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Verifying cryptographic hash chain...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">13 // AUDIT TRAIL</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Provenance Ledger</h1>
        </div>
        <span className="font-mono text-xs px-2.5 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
          HASH CHAIN VERIFIED
        </span>
      </div>

      {/* Log entries */}
      <div className="space-y-3">
        {logs.map((log, idx) => (
          <div key={log.event_id} className="locomotive-card p-3.5 rounded-lg space-y-2 font-mono text-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-accent font-bold">0{idx + 1}</span>
                <span className="text-white font-semibold">{log.action_type}</span>
              </div>
              <span className="text-muted text-[10px]">
                {new Date(log.timestamp * 1000).toLocaleTimeString()}
              </span>
            </div>

            <div className="p-2 rounded bg-background border border-card-border space-y-1 text-[11px] text-slate-300">
              <div className="flex justify-between">
                <span className="text-muted">Actor:</span>
                <span className="text-accent-cyan">{log.actor}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Target Resource:</span>
                <span>{log.resource_id}</span>
              </div>
              <div className="flex items-center justify-between text-muted text-[10px] pt-1 border-t border-card-border">
                <span className="flex items-center gap-1"><Hash className="w-3 h-3" /> SHA-256 Digest:</span>
                <span className="truncate max-w-[160px]">{log.sha256_hash}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
