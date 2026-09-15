import React, { useState, useEffect, useMemo } from 'react';
import { DeploymentTarget } from '../types';
import { mobileApi } from '../api/client';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SkeletonList } from '../components/ui/Skeleton';
import {
  Rocket,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Copy,
  Check,
  RefreshCw,
  Server,
  Smartphone,
  Database,
  Cloud,
  X,
  ShieldAlert,
} from 'lucide-react';

export const DeploymentsScreen: React.FC = () => {
  const [deployments, setDeployments] = useState<DeploymentTarget[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState<'all' | 'production' | 'device' | 'data'>('all');
  const [copiedField, setCopiedField] = useState<string | null>(null);

  // Rollback Modal State
  const [rollbackTarget, setRollbackTarget] = useState<DeploymentTarget | null>(null);
  const [rollbackReason, setRollbackReason] = useState('Production revert to previous stable release');
  const [rollingBack, setRollingBack] = useState(false);
  const [rollbackSuccess, setRollbackSuccess] = useState<string | null>(null);

  const fetchDeployments = async () => {
    try {
      const data = await mobileApi.getDeployments();
      setDeployments(data);
    } catch (err) {
      console.error('Failed to fetch deployments:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDeployments();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchDeployments();
  };

  const copyToClipboard = (text: string, fieldId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleTriggerRollback = async () => {
    if (!rollbackTarget) return;
    setRollingBack(true);
    try {
      await mobileApi.triggerRollback(rollbackTarget.id);
      setRollbackSuccess(`Successfully initiated rollback for ${rollbackTarget.service_name}`);
      setTimeout(() => {
        setRollbackTarget(null);
        setRollbackSuccess(null);
        fetchDeployments();
      }, 1500);
    } catch (err) {
      console.error('Rollback failed:', err);
    } finally {
      setRollingBack(false);
    }
  };

  const getProviderIcon = (provider: string) => {
    const p = provider.toLowerCase();
    if (p.includes('device') || p.includes('usb')) return <Smartphone className="w-4 h-4 text-[#E6391E]" />;
    if (p.includes('sqlite') || p.includes('database')) return <Database className="w-4 h-4 text-amber-600" />;
    if (p.includes('vercel') || p.includes('cloud')) return <Cloud className="w-4 h-4 text-blue-600" />;
    return <Server className="w-4 h-4 text-emerald-600" />;
  };

  const filteredDeployments = useMemo(() => {
    return deployments.filter((dep) => {
      const env = dep.environment.toLowerCase();
      if (activeFilter === 'production') return env.includes('production');
      if (activeFilter === 'device') return env.includes('device') || dep.provider.toLowerCase().includes('device');
      if (activeFilter === 'data') return env.includes('data') || dep.service_name.toLowerCase().includes('database') || dep.service_name.toLowerCase().includes('sqlite');
      return true;
    });
  }, [deployments, activeFilter]);

  const healthyCount = useMemo(() => {
    return deployments.filter((d) => d.status.toLowerCase() === 'healthy').length;
  }, [deployments]);

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh] animate-screen-enter pb-16">
      {/* Top Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase flex items-center gap-1.5">
            <Rocket className="w-3 h-3 text-[#E6391E]" />
            DEPLOYMENT RADAR • TARGETS & ROLLBACK
          </span>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1 text-[11px] font-mono font-bold text-zinc-600 hover:text-black transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin text-[#E6391E]' : ''}`} />
            <span>REFRESH</span>
          </button>
        </div>
        <h2 className="text-3xl font-headline font-bold text-[#0A0A0A] mt-1">
          Deployments
        </h2>
        <p className="font-sans text-xs text-zinc-500 mt-0.5">
          Live cluster endpoints, hardware companion targets, and atomic one-tap rollback switches.
        </p>
      </div>

      {/* Metrics Banner */}
      <div className="grid grid-cols-3 gap-2 my-3">
        <div className="border border-[#0A0A0A] p-2.5 bg-zinc-50 flex flex-col">
          <span className="font-mono text-[9px] text-zinc-500 uppercase">ACTIVE TARGETS</span>
          <span className="font-mono text-lg font-black text-[#0A0A0A] mt-0.5">
            {loading ? '...' : deployments.length}
          </span>
          <span className="font-mono text-[9px] text-zinc-400">monitored</span>
        </div>

        <div className="border border-[#0A0A0A] p-2.5 bg-zinc-50 flex flex-col">
          <span className="font-mono text-[9px] text-zinc-500 uppercase">HEALTH RATIO</span>
          <span className="font-mono text-lg font-black text-emerald-600 mt-0.5">
            {loading ? '...' : deployments.length > 0 ? `${Math.round((healthyCount / deployments.length) * 100)}%` : '100%'}
          </span>
          <span className="font-mono text-[9px] text-zinc-400">{healthyCount} healthy</span>
        </div>

        <div className="border border-[#0A0A0A] p-2.5 bg-zinc-50 flex flex-col">
          <span className="font-mono text-[9px] text-zinc-500 uppercase">ROLLBACK READY</span>
          <span className="font-mono text-lg font-black text-[#E6391E] mt-0.5">
            {loading ? '...' : deployments.filter((d) => d.rollback_available).length}
          </span>
          <span className="font-mono text-[9px] text-zinc-400">instant atomic</span>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px] font-mono scrollbar-none mb-3">
        {(['all', 'production', 'device', 'data'] as const).map((filter) => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            className={`px-3 py-1 border whitespace-nowrap font-bold transition-colors ${
              activeFilter === filter
                ? 'bg-[#0A0A0A] text-white border-[#0A0A0A]'
                : 'bg-white text-zinc-600 border-zinc-300 hover:border-black'
            }`}
          >
            {filter.toUpperCase()} ({filter === 'all' ? deployments.length : deployments.filter((d) => d.environment.includes(filter) || (filter === 'data' && d.service_name.toLowerCase().includes('sqlite'))).length})
          </button>
        ))}
      </div>

      {/* Deployments List */}
      <div className="flex-1 overflow-y-auto max-h-[50vh] space-y-3">
        {loading ? (
          <div className="p-4 space-y-3">
            <div className="p-4 flex items-center justify-center bg-zinc-50 border border-zinc-200">
              <LoadingSpinner size="md" label="Checking target cluster health..." />
            </div>
            <SkeletonList rows={3} />
          </div>
        ) : filteredDeployments.length === 0 ? (
          <div className="p-8 text-center font-mono text-xs text-zinc-400 space-y-1 border border-[#0A0A0A] bg-zinc-50">
            <Rocket className="w-8 h-8 text-zinc-300 mx-auto mb-2" />
            <p className="font-bold text-zinc-600">No matching deployment targets</p>
            <p className="text-[10px]">Change the filter tab to view all registered targets.</p>
          </div>
        ) : (
          filteredDeployments.map((dep) => {
            const isHealthy = dep.status.toLowerCase() === 'healthy';

            return (
              <div
                key={dep.id}
                className="border border-[#0A0A0A] p-4 bg-white hover:bg-zinc-50 card-tactile transition-smooth space-y-3"
              >
                {/* Top Row: Service Name + Health Badge */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 border border-zinc-300 bg-zinc-50">
                      {getProviderIcon(dep.provider)}
                    </div>
                    <div>
                      <h4 className="font-bold text-sm text-[#0A0A0A] leading-tight">
                        {dep.service_name}
                      </h4>
                      <span className="font-mono text-[10px] text-zinc-400 block mt-0.5">
                        {dep.provider} • {dep.environment}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <span
                      className={`inline-flex items-center gap-1 font-mono text-[9px] font-black px-2 py-0.5 border uppercase ${
                        isHealthy
                          ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                          : 'border-amber-600 bg-amber-50 text-amber-700'
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          isHealthy ? 'bg-emerald-600' : 'bg-amber-600 animate-ping'
                        }`}
                      />
                      {dep.status}
                    </span>
                  </div>
                </div>

                {/* Commit SHA and Live URL info */}
                <div className="p-2.5 bg-zinc-50 border border-zinc-200 font-mono text-xs space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-zinc-500 uppercase">HEAD COMMIT:</span>
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-[#E6391E]">{dep.commit_sha}</span>
                      <button
                        onClick={(e) => copyToClipboard(dep.commit_sha, dep.id + '-sha', e)}
                        className="text-zinc-400 hover:text-black"
                      >
                        {copiedField === dep.id + '-sha' ? (
                          <Check className="w-3 h-3 text-emerald-600" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[11px] pt-1 border-t border-zinc-200">
                    <span className="text-[10px] text-zinc-500 uppercase">ENDPOINT:</span>
                    <a
                      href={dep.live_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[#0A0A0A] hover:text-[#E6391E] flex items-center gap-1 truncate max-w-[200px] underline font-semibold"
                    >
                      <span className="truncate">{dep.live_url}</span>
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-between gap-2 pt-1">
                  <div className="font-mono text-[10px] text-zinc-400">
                    LAST DEPLOYED: {new Date(dep.last_deployed_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>

                  {dep.rollback_available ? (
                    <button
                      onClick={() => setRollbackTarget(dep)}
                      className="px-3 py-1.5 border border-[#E6391E] text-[#E6391E] bg-red-50 hover:bg-[#E6391E] hover:text-white font-mono text-[11px] font-bold flex items-center gap-1.5 transition-colors"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>ROLLBACK</span>
                    </button>
                  ) : (
                    <span className="font-mono text-[10px] text-zinc-400 border border-zinc-200 px-2 py-1 bg-zinc-100">
                      LOCKED
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer System Status */}
      <div className="border border-[#0A0A0A] p-3 bg-zinc-50 mt-3 flex items-center justify-between font-mono text-[11px]">
        <div className="flex items-center gap-1.5 text-zinc-600">
          <Server className="w-3.5 h-3.5 text-[#E6391E]" />
          <span>PRODUCTION FLEET ONLINE</span>
        </div>
        <button
          onClick={handleRefresh}
          className="font-bold text-[#E6391E] underline hover:text-black"
        >
          REFRESH TARGETS ↗
        </button>
      </div>

      {/* Rollback Confirmation Modal */}
      {rollbackTarget && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-white border-t-2 sm:border-2 border-[#E6391E] w-full max-w-md p-5 space-y-4 shadow-2xl animate-screen-enter">
            <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-3">
              <div className="flex items-center gap-2 text-[#E6391E]">
                <ShieldAlert className="w-5 h-5" />
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-[#0A0A0A]">
                  INSTANT ATOMIC ROLLBACK
                </span>
              </div>
              <button
                onClick={() => setRollbackTarget(null)}
                className="w-7 h-7 border border-[#0A0A0A] flex items-center justify-center hover:bg-black hover:text-white transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 bg-red-50 border border-[#E6391E] space-y-1">
                <span className="text-[10px] font-bold text-[#E6391E] uppercase block">TARGET SERVICE</span>
                <p className="font-bold text-sm text-[#0A0A0A]">{rollbackTarget.service_name}</p>
                <p className="text-[10px] text-zinc-600">
                  Current Commit: <span className="font-bold text-[#E6391E]">{rollbackTarget.commit_sha}</span> ({rollbackTarget.environment})
                </p>
              </div>

              <div>
                <label className="text-[10px] text-zinc-500 uppercase block mb-1">
                  ROLLBACK JUSTIFICATION (LOGGED TO AUDIT TRAIL)
                </label>
                <textarea
                  rows={2}
                  value={rollbackReason}
                  onChange={(e) => setRollbackReason(e.target.value)}
                  className="w-full p-2.5 text-xs font-mono bg-zinc-50 border border-[#0A0A0A] focus:outline-none focus:bg-white"
                />
              </div>

              {rollbackSuccess && (
                <div className="p-2.5 bg-emerald-50 border border-emerald-600 text-emerald-800 text-[11px] font-bold flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>{rollbackSuccess}</span>
                </div>
              )}
            </div>

            <div className="border-t border-zinc-200 pt-3 flex gap-2">
              <button
                onClick={() => setRollbackTarget(null)}
                disabled={rollingBack}
                className="flex-1 py-3 border border-[#0A0A0A] font-mono text-xs font-bold hover:bg-zinc-100 transition-colors"
              >
                CANCEL
              </button>
              <button
                onClick={handleTriggerRollback}
                disabled={rollingBack}
                className="flex-1 py-3 bg-[#E6391E] text-white font-mono text-xs font-bold hover:bg-black transition-colors flex items-center justify-center gap-1.5"
              >
                {rollingBack ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  <>
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>CONFIRM ROLLBACK</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
