import React from 'react';
import { ExecutiveOverview } from '../types';
import { Activity, ShieldAlert, Cpu, Smartphone, Server, GitPullRequest, ArrowUpRight } from 'lucide-react';

interface Props {
  overview: ExecutiveOverview;
  onNavigate: (screenId: any) => void;
}

export const DashboardScreen: React.FC<Props> = ({ overview, onNavigate }) => {
  const { telemetry, emergency_stop } = overview;

  return (
    <div className="space-y-6">
      {/* Header Index Tag */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">01 // EXECUTIVE RADAR</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Mission Control</h1>
        </div>
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center px-2.5 py-1 rounded text-xs font-mono font-medium ${
            emergency_stop.active ? 'bg-red-950 text-red-400 border border-red-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${emergency_stop.active ? 'bg-red-400' : 'bg-emerald-400 animate-pulse-dot'}`} />
            {emergency_stop.active ? 'EMERGENCY LOCKED' : 'SYSTEM HEALTHY'}
          </span>
        </div>
      </div>

      {/* Hero Stat Grid */}
      <div className="grid grid-cols-2 gap-3">
        <div 
          onClick={() => onNavigate('triage')}
          className="locomotive-card p-4 rounded-lg cursor-pointer hover:border-accent transition-colors"
        >
          <div className="flex items-center justify-between text-muted mb-2">
            <span className="font-mono text-xs">TRIAGE BACKLOG</span>
            <ArrowUpRight className="w-4 h-4 text-accent" />
          </div>
          <div className="font-display text-3xl font-bold text-white">{overview.triage_backlog_count}</div>
          <div className="text-xs text-muted mt-1">1 Critical Pending HITL</div>
        </div>

        <div 
          onClick={() => onNavigate('sprint_fleet')}
          className="locomotive-card p-4 rounded-lg cursor-pointer hover:border-accent-cyan transition-colors"
        >
          <div className="flex items-center justify-between text-muted mb-2">
            <span className="font-mono text-xs">ACTIVE SWARM</span>
            <Activity className="w-4 h-4 text-accent-cyan" />
          </div>
          <div className="font-display text-3xl font-bold text-white">{overview.active_sprint_workers}</div>
          <div className="text-xs text-muted mt-1">P14 Worktree Active</div>
        </div>
      </div>

      {/* Device & Hardware Card */}
      <div 
        onClick={() => onNavigate('hardware_telemetry')}
        className="locomotive-card p-4 rounded-lg border-l-2 border-l-accent-emerald cursor-pointer hover:bg-card/80 transition-colors"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Smartphone className="w-4 h-4 text-accent-emerald" />
            <span className="font-mono text-xs text-white font-medium">CONNECTED HARDWARE</span>
          </div>
          <span className="font-mono text-[11px] text-accent-emerald bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
            {telemetry.usb_device_serial}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-card-border font-mono text-xs">
          <div>
            <span className="text-muted block text-[10px]">DEVICE</span>
            <span className="text-white font-medium">{telemetry.usb_device_name.split(' ')[0]} 12</span>
          </div>
          <div>
            <span className="text-muted block text-[10px]">HOST CPU</span>
            <span className="text-white font-medium">{telemetry.host_cpu_percent}%</span>
          </div>
          <div>
            <span className="text-muted block text-[10px]">RAM LOAD</span>
            <span className="text-white font-medium">{telemetry.host_ram_percent}%</span>
          </div>
        </div>
      </div>

      {/* Locomotive Action Rows */}
      <div className="space-y-2">
        <span className="font-mono text-xs text-muted tracking-wider block mb-2">QUICK OPERATIONS</span>

        <div 
          onClick={() => onNavigate('voice_briefing')}
          className="locomotive-row flex items-center justify-between py-3 cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-accent">05</span>
            <div>
              <div className="font-display text-sm font-semibold text-white group-hover:text-accent transition-colors">
                Eva AI Voice CTO Briefing
              </div>
              <div className="text-xs text-muted">Sub-second duplex intake & status</div>
            </div>
          </div>
          <ArrowUpRight className="w-4 h-4 text-muted group-hover:text-accent" />
        </div>

        <div 
          onClick={() => onNavigate('pr_promotion')}
          className="locomotive-row flex items-center justify-between py-3 cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-accent-cyan">07</span>
            <div>
              <div className="font-display text-sm font-semibold text-white group-hover:text-accent-cyan transition-colors">
                One-Tap PR Merge & Promotion
              </div>
              <div className="text-xs text-muted">Fast-forward merge verified worktrees</div>
            </div>
          </div>
          <GitPullRequest className="w-4 h-4 text-muted group-hover:text-accent-cyan" />
        </div>

        <div 
          onClick={() => onNavigate('deployments')}
          className="locomotive-row flex items-center justify-between py-3 cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-accent-emerald">08</span>
            <div>
              <div className="font-display text-sm font-semibold text-white group-hover:text-accent-emerald transition-colors">
                Multi-Cloud Environments
              </div>
              <div className="text-xs text-muted">Vercel, Render & Supabase live health</div>
            </div>
          </div>
          <Server className="w-4 h-4 text-muted group-hover:text-accent-emerald" />
        </div>

        <div 
          onClick={() => onNavigate('emergency_stop')}
          className="locomotive-row flex items-center justify-between py-3 cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-red-500">14</span>
            <div>
              <div className="font-display text-sm font-semibold text-white group-hover:text-red-400 transition-colors">
                Emergency Tombstone Lock
              </div>
              <div className="text-xs text-muted">Instant founder hardware kill-switch</div>
            </div>
          </div>
          <ShieldAlert className="w-4 h-4 text-muted group-hover:text-red-400" />
        </div>
      </div>
    </div>
  );
};
