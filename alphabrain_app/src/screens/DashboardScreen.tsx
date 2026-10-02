import React, { useState, useEffect } from 'react';
import { DashboardScreenData, ExecutiveOverview, ScreenId, TaskSummary } from '../types';
import { mobileApi } from '../api/client';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SkeletonList } from '../components/ui/Skeleton';
import { Cpu, Sparkles, GitBranch, ArrowUpRight, Bot, UserCheck, Battery, BatteryCharging, PhoneCall } from 'lucide-react';

interface Props {
  overview: ExecutiveOverview;
  dashboardData?: DashboardScreenData | null;
  onNavigate: (screenId: ScreenId) => void;
}

export const DashboardScreen: React.FC<Props> = ({ overview, dashboardData: initialDashboard, onNavigate }) => {
  const [dashboard, setDashboard] = useState<DashboardScreenData | null>(() => {
    if (initialDashboard) return initialDashboard;
    if (typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem('swr:dashboard');
        return raw ? JSON.parse(raw) : null;
      } catch {
        return null;
      }
    }
    return null;
  });

  const [recentTasks, setRecentTasks] = useState<TaskSummary[]>(() => {
    if (typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem('swr:recentTasks');
        return raw ? JSON.parse(raw) : [];
      } catch {
        return [];
      }
    }
    return [];
  });

  const [activeWorktrees, setActiveWorktrees] = useState<Array<{ name: string; branch: string }>>(() => {
    if (typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem('swr:recentWorktrees');
        return raw ? JSON.parse(raw) : [];
      } catch {
        return [];
      }
    }
    return [];
  });

  const [loadingTasks, setLoadingTasks] = useState(() => {
    if (typeof window !== 'undefined') {
      return !localStorage.getItem('swr:recentTasks');
    }
    return true;
  });

  useEffect(() => {
    if (initialDashboard) {
      setDashboard(initialDashboard);
      try {
        localStorage.setItem('swr:dashboard', JSON.stringify(initialDashboard));
      } catch {}
    }
  }, [initialDashboard]);

  // Live polling: fetches lightweight paginated chunks (limit=3) every 4 seconds
  useEffect(() => {
    let active = true;

    const fetchLiveData = () => {
      mobileApi
        .getDashboard()
        .then((dash) => {
          if (active && dash) {
            setDashboard(dash);
            try {
              localStorage.setItem('swr:dashboard', JSON.stringify(dash));
            } catch {}
          }
        })
        .catch((err) => console.warn('Dashboard poll warning:', err));

      Promise.all([
        mobileApi.listTriage(undefined, 3, 0),
        mobileApi.getWorktrees(3, 0),
      ])
        .then(([tasks, worktrees]) => {
          if (active) {
            const topTasks = tasks.slice(0, 3);
            const topWts = worktrees.slice(0, 3);
            setRecentTasks(topTasks);
            setActiveWorktrees(topWts);
            setLoadingTasks(false);
            try {
              localStorage.setItem('swr:recentTasks', JSON.stringify(topTasks));
              localStorage.setItem('swr:recentWorktrees', JSON.stringify(topWts));
            } catch {}
          }
        })
        .catch((err) => {
          console.warn('Live tasks poll warning:', err);
          if (active) setLoadingTasks(false);
        });
    };

    fetchLiveData();
    const interval = setInterval(fetchLiveData, 4000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const emergencyStopActive = dashboard ? dashboard.emergency_stop.active : (overview?.emergency_stop?.active ?? false);
  const telemetry = dashboard ? dashboard.telemetry : (overview?.telemetry ?? {
    host_cpu_percent: 0,
    host_ram_percent: 0,
    host_ram_used_gb: 0,
    host_ram_total_gb: 16.0,
    thermal_pressure: 'nominal',
    battery_level_percent: 100,
    battery_charging: true,
    usb_device_connected: true,
    usb_device_serial: '10BF5P2AZF0010T',
    usb_device_name: 'iQOO 12 Flagship'
  });

  const cpuPercent = Math.round(telemetry.host_cpu_percent || 0);
  const ramPercent = Math.round(telemetry.host_ram_percent || 0);
  const ramUsed = telemetry.host_ram_used_gb ? telemetry.host_ram_used_gb.toFixed(1) : '0.0';
  const ramTotal = telemetry.host_ram_total_gb ? telemetry.host_ram_total_gb.toFixed(1) : '16.0';
  const batteryPercent = Math.round(telemetry.battery_level_percent ?? 100);
  const batteryCharging = telemetry.battery_charging ?? false;
  const quotasPercent = dashboard?.ai_quotas_percent ?? 96.6;
  const quotasSummary = dashboard?.ai_quotas_summary ?? '96.6% LEFT';

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] animate-screen-enter space-y-4">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
            MAC WORKSTATION
          </span>
          <span
            className={`font-mono text-[10px] font-bold px-2 py-0.5 border border-[#0A0A0A] transition-smooth ${
              emergencyStopActive ? 'bg-[#E6391E] text-white animate-pulse' : 'bg-white text-[#0A0A0A]'
            }`}
          >
            {emergencyStopActive ? 'EMERGENCY LOCKED' : (dashboard?.system_status ? dashboard.system_status.toUpperCase() : 'OPERATIONAL')}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-headline font-bold text-[#0A0A0A] mt-1">
              Command Center
            </h2>
            <p className="font-mono text-[11px] text-zinc-500 mt-0.5">
              Vitals, AI quotas & active sprints on host Mac
            </p>
          </div>
          <button
            onClick={() =>
              mobileApi.triggerSimulatedCall({
                caller_name: 'Eva (DeployMate CTO)',
                caller_role: 'Autonomous AI Architect',
                title: 'Urgent Architecture Review',
                prompt_summary: 'Founder sign-off requested for rate-limiting middleware deployment.',
                task_id: 'tsk_rate_limiter_99',
              })
            }
            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-mono text-[11px] font-bold transition-all shadow-sm hover-lift"
            title="Simulate incoming team VoIP call"
          >
            <PhoneCall className="w-3.5 h-3.5 animate-pulse" />
            <span>TEST TEAM CALL</span>
          </button>
        </div>
      </div>

      {/* SECTION 1: MAC HOST VITALS */}
      <div className="border border-[#0A0A0A] p-4 bg-white space-y-3">
        <div className="flex items-center justify-between border-b border-zinc-200 pb-2">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-[#0A0A0A]" />
            <span className="font-headline text-sm font-bold uppercase tracking-tight">Mac Host Vitals</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-pulse" />
            <span className="font-mono text-[10px] text-zinc-500 uppercase">
              {telemetry.thermal_pressure || 'Nominal'} Thermal
            </span>
          </div>
        </div>

        {/* CPU Meter */}
        <div className="space-y-1">
          <div className="flex items-center justify-between font-mono text-xs">
            <span className="text-zinc-600 font-medium">Apple Silicon CPU</span>
            <span className="font-bold text-[#0A0A0A]">{cpuPercent}%</span>
          </div>
          <div className="w-full h-2.5 bg-zinc-100 border border-[#0A0A0A] overflow-hidden p-[1px]">
            <div
              className={`h-full transition-all duration-500 ${
                cpuPercent > 80 ? 'bg-[#E6391E]' : 'bg-[#0A0A0A]'
              }`}
              style={{ width: `${Math.min(100, Math.max(4, cpuPercent))}%` }}
            />
          </div>
        </div>

        {/* RAM Meter */}
        <div className="space-y-1">
          <div className="flex items-center justify-between font-mono text-xs">
            <span className="text-zinc-600 font-medium">Unified Memory (RAM)</span>
            <span className="font-bold text-[#0A0A0A]">
              {ramPercent}% <span className="text-zinc-400 font-normal">({ramUsed} / {ramTotal} GB)</span>
            </span>
          </div>
          <div className="w-full h-2.5 bg-zinc-100 border border-[#0A0A0A] overflow-hidden p-[1px]">
            <div
              className={`h-full transition-all duration-500 ${
                ramPercent > 85 ? 'bg-[#E6391E]' : 'bg-[#0A0A0A]'
              }`}
              style={{ width: `${Math.min(100, Math.max(4, ramPercent))}%` }}
            />
          </div>
        </div>

        {/* Battery Meter */}
        <div className="space-y-1">
          <div className="flex items-center justify-between font-mono text-xs">
            <span className="text-zinc-600 font-medium flex items-center gap-1.5">
              {batteryCharging ? (
                <BatteryCharging className="w-3.5 h-3.5 text-[#E6391E]" />
              ) : (
                <Battery className="w-3.5 h-3.5 text-[#0A0A0A]" />
              )}
              Mac Battery
            </span>
            <span className="font-bold text-[#0A0A0A]">
              {batteryPercent}%{' '}
              <span className="text-zinc-400 font-normal">
                ({batteryCharging ? 'AC Charging' : 'Battery Power'})
              </span>
            </span>
          </div>
          <div className="w-full h-2.5 bg-zinc-100 border border-[#0A0A0A] overflow-hidden p-[1px]">
            <div
              className={`h-full transition-all duration-500 ${
                batteryPercent <= 20 ? 'bg-[#E6391E]' : 'bg-[#0A0A0A]'
              }`}
              style={{ width: `${Math.min(100, Math.max(4, batteryPercent))}%` }}
            />
          </div>
        </div>
      </div>

      {/* SECTION 2: AI MODEL QUOTAS */}
      <div
        onClick={() => onNavigate('model_router')}
        className="border border-[#0A0A0A] p-4 bg-white space-y-3 cursor-pointer hover:bg-zinc-50 card-tactile hover-lift transition-colors group"
      >
        <div className="flex items-center justify-between border-b border-zinc-200 pb-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#E6391E]" />
            <span className="font-headline text-sm font-bold uppercase tracking-tight">AI Model Quotas</span>
          </div>
          <div className="flex items-center gap-1 font-mono text-xs text-[#E6391E] font-bold group-hover:underline">
            <span>Details</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </div>
        </div>

        <div className="space-y-1">
          <div className="flex items-center justify-between font-mono text-xs">
            <span className="text-zinc-600 font-medium">Weekly Reserve Quota</span>
            <span className="font-bold text-[#E6391E]">{quotasSummary}</span>
          </div>
          <div className="w-full h-2.5 bg-zinc-100 border border-[#0A0A0A] overflow-hidden p-[1px]">
            <div
              className="h-full bg-[#E6391E] transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(4, quotasPercent))}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-1 font-mono text-[10px] text-zinc-500">
          <span>Active: Claude Opus 4.6 (OC-EDS Tier 1)</span>
          <span>8 Accounts Synced (Gemini + Claude)</span>
        </div>
      </div>


      {/* SECTION 3: ACTIVE WORKSPACES & SPRINTS (Started by Eva / Founder) */}
      <div className="border border-[#0A0A0A] p-4 bg-white space-y-3 flex-1 flex flex-col">
        <div className="flex items-center justify-between border-b border-zinc-200 pb-2">
          <div className="flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-[#0A0A0A]" />
            <span className="font-headline text-sm font-bold uppercase tracking-tight">Active Workspaces & Sprints</span>
          </div>
          <button
            onClick={() => onNavigate('triage')}
            className="flex items-center gap-1 font-mono text-xs text-[#0A0A0A] font-bold hover:text-[#E6391E] transition-colors"
          >
            <span>Triage Board</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {loadingTasks ? (
          <div className="py-4 space-y-2">
            <LoadingSpinner size="sm" label="Loading active sprints from host Mac..." />
            <SkeletonList rows={3} />
          </div>
        ) : recentTasks.length === 0 && activeWorktrees.length === 0 ? (
          <div className="py-4 text-center font-mono text-xs text-zinc-400">
            No active sprints running
          </div>
        ) : (
          <div className="divide-y divide-zinc-100 flex-1 space-y-1">
            {recentTasks.map((task) => (
              <div
                key={task.task_id}
                onClick={() => onNavigate('triage')}
                className="py-2 flex items-start justify-between hover:bg-zinc-50 px-1 cursor-pointer card-tactile hover-lift transition-colors"
              >
                <div className="space-y-0.5 max-w-[260px]">
                  <div className="flex items-center gap-1.5">
                    {task.author.toLowerCase().includes('eva') ? (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 border border-[#E6391E] text-[#E6391E] font-mono text-[8px] font-bold uppercase">
                        <Bot className="w-2.5 h-2.5" />
                        Eva SPRINT
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 border border-[#0A0A0A] text-[#0A0A0A] font-mono text-[8px] font-bold uppercase">
                        <UserCheck className="w-2.5 h-2.5" />
                        FOUNDER
                      </span>
                    )}
                    <span className="font-mono text-[9px] text-zinc-400 uppercase">
                      {task.category}
                    </span>
                  </div>
                  <div className="font-headline text-xs font-bold text-[#0A0A0A] truncate">
                    {task.title}
                  </div>
                </div>
                <span className="font-mono text-[9px] uppercase px-1.5 py-0.5 border border-zinc-300 text-zinc-600 shrink-0">
                  {task.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
