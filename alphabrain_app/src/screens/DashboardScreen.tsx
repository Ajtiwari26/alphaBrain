import React, { useState, useEffect } from 'react';
import { DashboardScreenData, ExecutiveOverview, ScreenId } from '../types';
import { mobileApi } from '../api/client';

interface Props {
  overview: ExecutiveOverview;
  dashboardData?: DashboardScreenData | null;
  onNavigate: (screenId: ScreenId) => void;
}

export const DashboardScreen: React.FC<Props> = ({ overview, dashboardData: initialDashboard, onNavigate }) => {
  const [dashboard, setDashboard] = useState<DashboardScreenData | null>(initialDashboard || null);

  useEffect(() => {
    if (initialDashboard) {
      setDashboard(initialDashboard);
    }
  }, [initialDashboard]);

  const emergencyStopActive = dashboard ? dashboard.emergency_stop.active : (overview?.emergency_stop?.active ?? false);
  const telemetry = dashboard ? dashboard.telemetry : (overview?.telemetry ?? { host_cpu_percent: 0, host_ram_percent: 0, host_ram_used_gb: 0, host_ram_total_gb: 0, thermal_pressure: 'nominal', battery_level_percent: 0, battery_charging: false, usb_device_connected: false, usb_device_serial: '---', usb_device_name: 'None' });
  const quotasSummary = dashboard ? dashboard.ai_quotas_summary : '---';
  const activeProjects = dashboard ? `${dashboard.active_projects_count} ACTIVE` : '---';
  const techDeptAgents = dashboard ? `${dashboard.tech_dept_agents_count} AGENTS` : (overview?.active_sprint_workers ? `${overview.active_sprint_workers} AGENTS` : '---');
  const triagePending = dashboard ? `${dashboard.triage_pending_count} PENDING` : (overview?.triage_backlog_count ? `${overview.triage_backlog_count} PENDING` : '---');
  const worktreesSummary = dashboard ? dashboard.worktrees_summary : '---';
  const hardwareSerial = dashboard ? dashboard.hardware_sync_serial : (overview?.telemetry?.usb_device_serial || '---');

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] animate-screen-enter">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          MISSION KERNEL
        </span>
        <div className="flex items-center justify-between mt-1">
          <h2 className="text-3xl font-headline font-bold text-[#0A0A0A]">
            Command Center
          </h2>
          <span
            className={`font-mono text-[10px] font-bold px-2 py-0.5 border border-[#0A0A0A] transition-smooth ${
              emergencyStopActive ? 'bg-[#E6391E] text-white animate-pulse' : 'bg-white text-[#0A0A0A]'
            }`}
          >
            {emergencyStopActive ? 'LOCKED' : (dashboard?.system_status ? dashboard.system_status.toUpperCase() : 'CONNECTING...')}
          </span>
        </div>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-2">
        {/* Row 01: System Live */}
        <div
          onClick={() => onNavigate('overview')}
          className="py-4 px-1 flex items-center justify-between hover:bg-black hover:text-white card-tactile hover-lift transition-smooth cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-zinc-400 group-hover:text-zinc-300">01</span>
            <span className="font-medium text-base">System Live</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-zinc-500 group-hover:text-zinc-300">
              CPU {telemetry.host_cpu_percent}% // RAM {telemetry.host_ram_percent}%
            </span>
            <span className="w-2.5 h-2.5 rounded-full bg-[#E6391E] animate-pulse" />
            <span className="text-sm font-bold text-[#E6391E] group-hover:text-white">↗</span>
          </div>
        </div>

        {/* Row 02: AI Quotas */}
        <div
          onClick={() => onNavigate('model_router')}
          className="py-4 px-1 flex items-center justify-between hover:bg-black hover:text-white transition-colors cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-zinc-400 group-hover:text-zinc-300">02</span>
            <span className="font-medium text-base">AI Quotas</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-[#E6391E] group-hover:text-white">
              {quotasSummary}
            </span>
            <span className="text-sm font-bold text-[#E6391E] group-hover:text-white">↗</span>
          </div>
        </div>

        {/* Row 03: Active Projects */}
        <div
          onClick={() => onNavigate('projects')}
          className="py-4 px-1 flex items-center justify-between hover:bg-black hover:text-white transition-colors cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-zinc-400 group-hover:text-zinc-300">03</span>
            <span className="font-medium text-base">Active Projects</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-zinc-500 group-hover:text-zinc-300">
              {activeProjects}
            </span>
            <span className="text-sm font-bold text-[#E6391E] group-hover:text-white">↗</span>
          </div>
        </div>

        {/* Row 04: Tech Dept */}
        <div
          onClick={() => onNavigate('tech_dept')}
          className="py-4 px-1 flex items-center justify-between hover:bg-black hover:text-white transition-colors cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-zinc-400 group-hover:text-zinc-300">04</span>
            <span className="font-medium text-base">Tech Dept</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-zinc-500 group-hover:text-zinc-300">
              {techDeptAgents}
            </span>
            <span className="text-sm font-bold text-[#E6391E] group-hover:text-white">↗</span>
          </div>
        </div>

        {/* Row 05: Triage Board */}
        <div
          onClick={() => onNavigate('triage')}
          className="py-4 px-1 flex items-center justify-between hover:bg-black hover:text-white transition-colors cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-zinc-400 group-hover:text-zinc-300">05</span>
            <span className="font-medium text-base">Triage Board</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-[#E6391E] group-hover:text-white">
              {triagePending}
            </span>
            <span className="text-sm font-bold text-[#E6391E] group-hover:text-white">↗</span>
          </div>
        </div>

        {/* Row 06: Worktree Manager */}
        <div
          onClick={() => onNavigate('worktrees')}
          className="py-4 px-1 flex items-center justify-between hover:bg-black hover:text-white transition-colors cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-zinc-400 group-hover:text-zinc-300">06</span>
            <span className="font-medium text-base">Git Worktrees</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-zinc-500 group-hover:text-zinc-300">
              {worktreesSummary}
            </span>
            <span className="text-sm font-bold text-[#E6391E] group-hover:text-white">↗</span>
          </div>
        </div>
      </div>

      {/* Quick Status Footer Banner */}
      <div className="mt-4 p-4 border border-[#0A0A0A] bg-zinc-50 flex items-center justify-between">
        <span className="font-mono text-xs font-bold text-[#0A0A0A]">HARDWARE SYNC</span>
        <span className="font-mono text-xs font-bold text-[#E6391E]">
          CONNECTED ({hardwareSerial})
        </span>
      </div>
    </div>
  );
};
