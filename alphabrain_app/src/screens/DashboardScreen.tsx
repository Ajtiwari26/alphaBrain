import React from 'react';
import { ExecutiveOverview, ScreenId } from '../types';

interface Props {
  overview: ExecutiveOverview;
  onNavigate: (screenId: ScreenId) => void;
}

export const DashboardScreen: React.FC<Props> = ({ overview, onNavigate }) => {
  const { emergency_stop, triage_backlog_count, active_sprint_workers, telemetry } = overview;

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          MISSION KERNEL
        </span>
        <div className="flex items-center justify-between mt-1">
          <h2 className="text-3xl font-headline font-bold text-[#0A0A0A]">
            Command Center
          </h2>
          <span
            className={`font-mono text-[10px] font-bold px-2 py-0.5 border border-[#0A0A0A] ${
              emergency_stop.active ? 'bg-[#E6391E] text-white' : 'bg-white text-[#0A0A0A]'
            }`}
          >
            {emergency_stop.active ? 'LOCKED' : 'SYSTEM LIVE'}
          </span>
        </div>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-2">
        {/* Row 01: System Live */}
        <div
          onClick={() => onNavigate('overview')}
          className="py-4 px-1 flex items-center justify-between hover:bg-black hover:text-white transition-colors cursor-pointer group"
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
              85% LEFT
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
              3 ACTIVE
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
              {active_sprint_workers} AGENTS
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
              {triage_backlog_count} PENDING
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
              P14.1 MERGED
            </span>
            <span className="text-sm font-bold text-[#E6391E] group-hover:text-white">↗</span>
          </div>
        </div>
      </div>

      {/* Quick Status Footer Banner */}
      <div className="mt-4 p-4 border border-[#0A0A0A] bg-zinc-50 flex items-center justify-between">
        <span className="font-mono text-xs font-bold text-[#0A0A0A]">HARDWARE SYNC</span>
        <span className="font-mono text-xs font-bold text-[#E6391E]">
          CONNECTED ({telemetry.usb_device_serial || '10BF5P2AZF0010T'})
        </span>
      </div>
    </div>
  );
};
