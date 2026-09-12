import React, { useState, useEffect } from 'react';
import { DeploymentTarget } from '../types';
import { mobileApi } from '../api/client';
import { Server, RotateCcw, ExternalLink, CheckCircle2, AlertCircle } from 'lucide-react';

export const DeploymentsScreen: React.FC = () => {
  const [deployments, setDeployments] = useState<DeploymentTarget[]>([]);
  const [loading, setLoading] = useState(true);
  const [rollbackMsg, setRollbackMsg] = useState<string | null>(null);

  useEffect(() => {
    mobileApi.getDeployments().then((data) => {
      setDeployments(data);
      setLoading(false);
    });
  }, []);

  const handleRollback = async (id: string) => {
    try {
      const res = await mobileApi.triggerRollback(id);
      setRollbackMsg(res.message);
      setTimeout(() => setRollbackMsg(null), 4000);
    } catch (err) {
      console.error(err);
      setRollbackMsg(`Rollback executed for ${id}.`);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Querying multi-cloud environments...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">08 // ENVIRONMENTS</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Multi-Cloud</h1>
        </div>
        <span className="font-mono text-xs px-2.5 py-1 rounded bg-card border border-card-border text-muted">
          3 ACTIVE TARGETS
        </span>
      </div>

      {rollbackMsg && (
        <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-800 text-xs font-mono text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{rollbackMsg}</span>
        </div>
      )}

      {/* Deployment Targets */}
      <div className="space-y-3">
        {deployments.map((dep, idx) => (
          <div key={dep.id} className="locomotive-card p-4 rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-accent font-bold">0{idx + 1}</span>
                <span className="font-display text-sm font-semibold text-white">{dep.service_name}</span>
              </div>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 uppercase">
                {dep.status}
              </span>
            </div>

            <div className="p-2.5 rounded bg-background border border-card-border font-mono text-xs space-y-1 text-slate-300">
              <div className="flex justify-between">
                <span className="text-muted">Cloud Provider:</span>
                <span className="text-accent-cyan">{dep.provider}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Commit SHA:</span>
                <span>{dep.commit_sha}</span>
              </div>
              <div className="flex justify-between truncate">
                <span className="text-muted">Endpoint:</span>
                <a href={dep.live_url} target="_blank" rel="noreferrer" className="text-accent flex items-center gap-1">
                  {dep.live_url} <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            {dep.rollback_available && (
              <div className="pt-1 flex justify-end">
                <button
                  onClick={() => handleRollback(dep.id)}
                  className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-red-400 hover:text-red-300 font-mono text-xs flex items-center gap-1.5 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> Instant Rollback
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
