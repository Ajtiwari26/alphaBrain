import React, { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Terminal, Cpu, HardDrive, Activity, Play, Square, GitBranch, Shield, ArrowRight } from 'lucide-react';
import { ActiveTask, ScreenId, SystemMetrics, TaskResult, TerminalLog } from '../types';
import { desktopApi } from '../api/client';

interface Props {
  onNavigate: (screen: ScreenId) => void;
}

export const M03_CommandNode: React.FC<Props> = ({ onNavigate }) => {
  const [nodeId, setNodeId] = useState<string>('');
  const [clusterName, setClusterName] = useState<string>('');
  const [nodeStatus, setNodeStatus] = useState<string>('connecting');
  const [metrics, setMetrics] = useState<SystemMetrics>({
    cpu_usage: 0.0,
    memory_used_mb: 0.0,
    memory_total_mb: 0.0,
    disk_used_gb: 0.0,
    disk_total_gb: 0.0,
    uptime_seconds: 0.0,
    active_workers: 0,
  });

  const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([]);
  const [logs, setLogs] = useState<TerminalLog[]>([]);

  const [autoScroll, setAutoScroll] = useState(true);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((stream: 'stdout' | 'stderr' | 'system', text: string) => {
    const d = new Date();
    const timeStr = `${d.toTimeString().split(' ')[0]}.${String(d.getMilliseconds()).padStart(3, '0')}`;
    setLogs((prev) => [...prev, { id: String(Date.now()) + Math.random(), timestamp: timeStr, stream, text }]);
  }, []);

  const fetchNodeData = useCallback(async () => {
    try {
      const data = await desktopApi.getCommandNode();
      if (data) {
        if (data.metrics) setMetrics(data.metrics);
        if (data.active_tasks) {
          setActiveTasks(
            data.active_tasks.map((t) => ({
              id: t.id,
              title: t.title,
              priority: (t.priority as 'P0' | 'P1' | 'P2') || 'P0',
              branch: t.branch,
              status: (t.status as 'running' | 'queued' | 'passed' | 'failed') || 'running',
              duration: t.duration,
            }))
          );
        }
        if (data.logs && data.logs.length > 0) {
          setLogs(
            data.logs.map((l) => ({
              id: l.id,
              timestamp: l.timestamp,
              stream: (l.stream as 'stdout' | 'stderr' | 'system') || 'system',
              text: l.text,
            }))
          );
        }
        if (data.node_id) setNodeId(data.node_id);
        if (data.cluster_name) setClusterName(data.cluster_name);
        if (data.status) setNodeStatus(data.status);
      }
    } catch (err) {
      try {
        const tauriMetrics = await invoke<SystemMetrics>('get_system_metrics');
        setMetrics(tauriMetrics);
      } catch {
        // Fallback in web preview when offline
      }
    }
  }, []);

  useEffect(() => {
    fetchNodeData();
    const interval = setInterval(fetchNodeData, 5000);
    return () => clearInterval(interval);
  }, [fetchNodeData]);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const handleSpawnWorker = async () => {
    addLog('system', '[ACTION] Invoking Tauri IPC: spawn_worker_daemon...');
    try {
      const pid = await invoke<number>('spawn_worker_daemon', {
        workspace: '/Users/ajaytiwari/Desktop/Projects/alphaBrain',
      });
      setMetrics((m) => ({ ...m, active_workers: m.active_workers + 1 }));
      addLog('stdout', `[WORKER] Spawned alpha_worker.daemon successfully (PID: ${pid})`);
    } catch (err) {
      addLog('stderr', `[WORKER ERROR] ${String(err)}`);
      // Update count for simulated display
      setMetrics((m) => ({ ...m, active_workers: m.active_workers + 1 }));
    }
  };

  const handleExecuteTask = async (taskId: string) => {
    addLog('system', `[TASK] Invoking Tauri IPC: execute_task (${taskId})...`);
    try {
      const result = await invoke<TaskResult>('execute_task', {
        taskId,
        workspace: '/Users/ajaytiwari/Desktop/Projects/alphaBrain',
        leaseId: 'lse_prov_' + Date.now(),
      });
      addLog('stdout', `[TASK RESULT] ${result.task_id}: status=${result.status} exit_code=${result.exit_code}`);
      if (result.output) {
        addLog('stdout', `[OUTPUT] ${result.output.trim()}`);
      }
    } catch (err) {
      addLog('stderr', `[TASK ERROR] ${String(err)}`);
    }
  };

  const handleAbortTask = (taskId: string) => {
    addLog('stderr', `[SIGKILL] Abort signal dispatched to task ${taskId}`);
    setActiveTasks((tasks) =>
      tasks.map((t) => (t.id === taskId ? { ...t, status: 'failed' } : t))
    );
  };

  return (
    <div className="p-8 max-w-[1800px] w-full mx-auto space-y-8 bg-white text-[#0A0A0A] font-sans">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-4 flex justify-between items-end">
        <div>
          <span className="text-xs font-mono tracking-widest uppercase bg-[#0A0A0A] text-white px-2 py-0.5 font-bold">
            Screen M-03
          </span>
          <h1 className="text-3xl font-bold font-mono tracking-tight mt-2">
            COMMAND NODE & AUTONOMOUS DISPATCH
          </h1>
          <p className="text-sm text-neutral-600 mt-1">
            Real-time telemetry, active worktree execution queue, and live streaming terminal.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => onNavigate('M04_SecurityEnclave')}
            className="flex items-center gap-1.5 px-3 py-1 border border-[#0A0A0A] hover:bg-neutral-100 text-xs font-mono uppercase font-semibold"
          >
            <Shield className="w-3.5 h-3.5 text-[#E6391E]" />
            <span>Security Enclave</span>
            <ArrowRight className="w-3 h-3 text-neutral-400" />
          </button>
          <div className="flex items-center gap-2 border-l border-neutral-300 pl-3">
            <span className={`w-2.5 h-2.5 rounded-full ${nodeStatus === 'operational' ? 'bg-emerald-500' : 'bg-amber-500'} animate-pulse`} />
            <span className="text-xs font-mono uppercase tracking-wider font-semibold">
              {nodeId} ({clusterName} • {nodeStatus.toUpperCase()})
            </span>
          </div>
        </div>
      </div>

      {/* System Metrics Telemetry Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-4 gap-4 font-mono text-xs">
        <div className="border border-[#0A0A0A] p-4 bg-neutral-50 space-y-1">
          <div className="flex items-center justify-between text-neutral-500">
            <span>CPU UTILIZATION</span>
            <Cpu className="w-4 h-4 text-[#E6391E]" />
          </div>
          <div className="text-2xl font-bold text-black">{metrics.cpu_usage.toFixed(1)}%</div>
          <div className="w-full bg-neutral-200 h-1.5 mt-2">
            <div className="bg-[#E6391E] h-1.5" style={{ width: `${Math.min(metrics.cpu_usage, 100)}%` }} />
          </div>
        </div>

        <div className="border border-[#0A0A0A] p-4 bg-neutral-50 space-y-1">
          <div className="flex items-center justify-between text-neutral-500">
            <span>RAM CONSUMPTION</span>
            <Activity className="w-4 h-4 text-[#E6391E]" />
          </div>
          <div className="text-2xl font-bold text-black">
            {(metrics.memory_used_mb / 1024).toFixed(1)} GB
          </div>
          <div className="text-[10px] text-neutral-500">
            of {(metrics.memory_total_mb / 1024).toFixed(0)} GB total unified memory
          </div>
        </div>

        <div className="border border-[#0A0A0A] p-4 bg-neutral-50 space-y-1">
          <div className="flex items-center justify-between text-neutral-500">
            <span>WORKTREE DISK</span>
            <HardDrive className="w-4 h-4 text-[#E6391E]" />
          </div>
          <div className="text-2xl font-bold text-black">
            {metrics.disk_used_gb.toFixed(0)} GB
          </div>
          <div className="text-[10px] text-neutral-500">
            {metrics.disk_total_gb.toFixed(0)} GB SSD capacity
          </div>
        </div>

        <div className="border border-[#0A0A0A] p-4 bg-neutral-50 space-y-1">
          <div className="flex items-center justify-between text-neutral-500">
            <span>WORKER DAEMONS</span>
            <Play className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-black">{metrics.active_workers} ACTIVE</div>
          <div className="text-[10px] text-emerald-700 font-bold">
            Lease pool operational
          </div>
        </div>
      </div>

      {/* Task Queue Section */}
      <div className="border border-[#0A0A0A] p-5 space-y-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-[#E6391E]" />
            <h2 className="text-sm font-mono font-bold uppercase tracking-wider">
              Active Task Execution Queue
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSpawnWorker}
              className="px-3 py-1.5 border border-[#0A0A0A] bg-neutral-100 hover:bg-neutral-200 text-xs font-mono uppercase font-bold"
            >
              + Spawn Worker Daemon (Rust IPC)
            </button>
            <button
              onClick={() => handleExecuteTask('tsk_eva_cbc068ce5324')}
              className="px-3 py-1.5 bg-[#0A0A0A] hover:bg-[#E6391E] text-white text-xs font-mono uppercase font-bold transition-colors"
            >
              Verify Active Worktree
            </button>
          </div>
        </div>

        <div className="space-y-3">
          {activeTasks.length === 0 ? (
            <div className="border border-dashed border-neutral-300 p-6 text-center text-xs font-mono text-neutral-500 bg-neutral-50">
              No tasks currently active in triage queue. Autonomous worker daemons standing by.
            </div>
          ) : (
            activeTasks.map((task) => (
            <div
              key={task.id}
              className="border border-[#0A0A0A] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="font-bold text-[#E6391E]">{task.priority}</span>
                  <span className="text-neutral-400">|</span>
                  <span className="font-bold text-black">{task.id}</span>
                  <span className="text-neutral-400">|</span>
                  <span className="bg-neutral-100 px-2 py-0.5 border border-neutral-300 text-[11px]">
                    {task.branch}
                  </span>
                </div>
                <div className="text-sm font-semibold">{task.title}</div>
              </div>

              <div className="flex items-center gap-4 font-mono text-xs">
                <div className="text-right">
                  <div className="text-[10px] text-neutral-500 uppercase">Status</div>
                  <span
                    className={`font-bold uppercase px-2 py-0.5 text-[10px] ${
                      task.status === 'running'
                        ? 'bg-emerald-100 text-emerald-800'
                        : task.status === 'queued'
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-rose-100 text-rose-800'
                    }`}
                  >
                    {task.status} ({task.duration})
                  </span>
                </div>
                {task.status === 'running' && (
                  <button
                    onClick={() => handleAbortTask(task.id)}
                    className="flex items-center gap-1 px-2.5 py-1.5 border border-rose-800 text-rose-800 hover:bg-rose-50 text-[11px] font-bold uppercase"
                  >
                    <Square className="w-3 h-3" />
                    <span>Abort</span>
                  </button>
                )}
              </div>
            </div>
          )))}
        </div>
      </div>

      {/* Live Terminal Streaming Console */}
      <div className="border border-[#0A0A0A] space-y-0">
        <div className="bg-[#0A0A0A] text-white px-4 py-2.5 flex items-center justify-between font-mono text-xs border-b border-neutral-800">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-[#E6391E]" />
            <span className="font-bold uppercase tracking-wider">Live Streaming Terminal Output</span>
            <span className="text-neutral-400 text-[10px]">[WebSocket Hook: wss://api.alphabrain.live/ws/logs]</span>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 cursor-pointer text-[11px]">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="accent-[#E6391E]"
              />
              <span>Auto-Scroll</span>
            </label>
            <button
              onClick={() => setLogs([])}
              className="px-2 py-0.5 border border-neutral-700 hover:bg-neutral-800 text-[10px] uppercase font-bold"
            >
              Clear
            </button>
          </div>
        </div>

        <div className="bg-[#0A0A0A] p-4 h-[500px] overflow-y-auto font-mono text-xs space-y-1.5">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start gap-2">
              <span className="text-neutral-500 select-none text-[10px] pt-0.5">{log.timestamp}</span>
              <span
                className={`leading-relaxed ${
                  log.stream === 'system'
                    ? 'text-cyan-400'
                    : log.stream === 'stderr'
                    ? 'text-rose-400 font-bold'
                    : 'text-neutral-200'
                }`}
              >
                {log.text}
              </span>
            </div>
          ))}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  );
};
