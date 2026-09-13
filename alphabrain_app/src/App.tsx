import React, { useState, useEffect } from 'react';
import { ScreenId, ExecutiveOverview } from './types';
import { mobileApi } from './api/client';
import {
  LayoutDashboard,
  Inbox,
  GitBranch,
  Cpu,
  Menu,
  X,
  Smartphone,
  Layers,
  Terminal,
  RotateCcw,
} from 'lucide-react';

import { SplashScreen } from './screens/SplashScreen';
import { AuthScreen } from './screens/AuthScreen';
import { InstanceSyncScreen } from './screens/InstanceSyncScreen';
import { DashboardScreen } from './screens/DashboardScreen';
import { ModelRouterScreen } from './screens/ModelRouterScreen';
import { DepartmentsScreen } from './screens/DepartmentsScreen';
import { AgentCommsScreen } from './screens/AgentCommsScreen';
import { TechDeptScreen } from './screens/TechDeptScreen';
import { WorktreesScreen } from './screens/WorktreesScreen';
import { TriageQueueScreen } from './screens/TriageQueueScreen';
import { LiveStreamScreen } from './screens/LiveStreamScreen';
import { DeploymentsScreen } from './screens/DeploymentsScreen';
import { ProjectsScreen } from './screens/ProjectsScreen';
import { SettingsScreen } from './screens/SettingsScreen';

const ALL_SCREENS: Array<{ id: ScreenId; num: string; title: string; category: string }> = [
  { id: 'splash', num: '01', title: 'Splash Boot', category: 'Brand' },
  { id: 'auth', num: '02', title: 'Founder Access', category: 'Security' },
  { id: 'instance_sync', num: '03', title: 'Instance Sync', category: 'Hardware' },
  { id: 'overview', num: '04', title: 'Command Center', category: 'Mission' },
  { id: 'model_router', num: '05', title: 'AI Quotas', category: 'Models' },
  { id: 'departments', num: '06', title: 'Departments', category: 'Structure' },
  { id: 'agent_comms', num: '07', title: 'Agent Comms', category: 'Mesh' },
  { id: 'tech_dept', num: '08', title: 'Tech Dept', category: 'Tech' },
  { id: 'worktrees', num: '09', title: 'Worktrees', category: 'Git' },
  { id: 'triage', num: '10', title: 'Triage Board', category: 'Intake' },
  { id: 'live_stream', num: '11', title: 'Live Stream', category: 'Logs' },
  { id: 'deployments', num: '12', title: 'Deploy Targets', category: 'Deploy' },
  { id: 'projects', num: '13', title: 'Project Portfolio', category: 'Portfolio' },
  { id: 'settings', num: '14', title: 'Global Settings', category: 'Founder' },
];

export function App() {
  // Session lifecycle stages: 'splash' -> 'auth' -> 'instance_sync' -> 'authenticated'
  const [sessionStage, setSessionStage] = useState<'splash' | 'auth' | 'instance_sync' | 'authenticated'>(() => {
    if (typeof window !== 'undefined') {
      const saved = sessionStorage.getItem('alpha_session_stage');
      if (saved === 'authenticated') return 'authenticated';
    }
    return 'splash';
  });

  const [currentScreen, setCurrentScreen] = useState<ScreenId>(() => {
    if (typeof window !== 'undefined') {
      const saved = sessionStorage.getItem('alpha_session_stage');
      if (saved === 'authenticated') return 'overview';
    }
    return 'splash';
  });

  const [menuOpen, setMenuOpen] = useState(false);
  const [overview, setOverview] = useState<ExecutiveOverview | null>(null);

  useEffect(() => {
    mobileApi
      .getOverview()
      .then(setOverview)
      .catch((err) => {
        console.warn('Backend overview fetch warning (using offline state):', err);
        setOverview({
          app_version: '1.0.0',
          system_status: 'OFFLINE',
          emergency_stop: {
            active: false,
            locked_at: null,
            lock_file: '',
            reason: '',
            triggered_by: '',
          },
          telemetry: {
            host_cpu_percent: 0.0,
            host_ram_percent: 0.0,
            host_ram_used_gb: 0.0,
            host_ram_total_gb: 0.0,
            thermal_pressure: 'unknown',
            battery_level_percent: 0,
            battery_charging: false,
            usb_device_connected: false,
            usb_device_serial: '10BF5P2AZF0010T',
            usb_device_name: 'iQOO 12 Flagship',
          },
          triage_backlog_count: 0,
          active_sprint_workers: 0,
          recent_deployments_count: 0,
          eva_status: 'OFFLINE',
        });
      });
  }, [currentScreen]);

  const handleSplashContinue = () => {
    setSessionStage('auth');
    setCurrentScreen('auth');
  };

  const handleAuthenticated = () => {
    setSessionStage('instance_sync');
    setCurrentScreen('instance_sync');
  };

  const handleSynced = () => {
    setSessionStage('authenticated');
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('alpha_session_stage', 'authenticated');
    }
    setCurrentScreen('overview');
  };

  const handleResetSession = () => {
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('alpha_session_stage');
    }
    setSessionStage('splash');
    setCurrentScreen('splash');
    setMenuOpen(false);
  };

  const navigateTo = (screen: ScreenId) => {
    // Only allow jumping directly to internal fleet screens once authenticated
    if (sessionStage !== 'authenticated' && !['splash', 'auth', 'instance_sync'].includes(screen)) {
      return;
    }
    setCurrentScreen(screen);
    setMenuOpen(false);
  };

  return (
    <div className="min-h-screen bg-white text-[#0A0A0A] flex flex-col font-sans max-w-md mx-auto relative border-x border-[#0A0A0A] selection:bg-[#E6391E] selection:text-white">
      {/* Top Header Bar with Safe-Area Notch Inset (Only visible in authenticated Command Center & Fleet screens) */}
      {sessionStage === 'authenticated' && (
        <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-[#0A0A0A] px-4 pt-[max(env(safe-area-inset-top),2.5rem)] pb-3 flex items-center justify-between">
          <div
            onClick={() => navigateTo('overview')}
            className="flex items-center gap-2.5 cursor-pointer group"
          >
            <div className="w-7 h-7 bg-[#0A0A0A] flex items-center justify-center font-headline font-bold text-white text-xs group-hover:scale-105 transition-transform">
              <span className="text-[#E6391E] font-mono mr-0.5">α</span>B
            </div>
            <div>
              <div className="font-headline font-bold text-sm tracking-tight leading-none text-[#0A0A0A]">
                AlphaBrain
              </div>
              <div className="font-mono text-[9px] text-zinc-500 tracking-widest mt-0.5 uppercase flex items-center gap-1">
                <span>DeployMate</span>
                <span className="text-[#E6391E]">• LIVE</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="font-mono text-[10px] text-[#0A0A0A] bg-zinc-100 border border-[#0A0A0A] px-2 py-0.5 flex items-center gap-1">
              <Smartphone className="w-3 h-3 text-[#E6391E]" />
              <span className="font-semibold">10BF5P2AZF0010T</span>
            </div>

            <button
              title="Lock / Reset Flow"
              onClick={handleResetSession}
              className="w-8 h-8 bg-white border border-[#0A0A0A] flex items-center justify-center text-zinc-600 hover:text-black hover:bg-zinc-100 btn-tactile"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="w-8 h-8 bg-white border border-[#0A0A0A] flex items-center justify-center text-[#0A0A0A] hover:bg-zinc-100 transition-colors btn-tactile"
            >
              {menuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </header>
      )}

      {/* Screen Drawer Overlay (14-Screen Locomotive Directory) */}
      {menuOpen && (
        <div className="absolute inset-0 z-50 bg-white/98 backdrop-blur p-5 pt-[max(env(safe-area-inset-top),2.5rem)] overflow-y-auto space-y-4 animate-screen-enter">
          <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-3">
            <div>
              <span className="font-mono text-xs text-[#E6391E] font-bold">
                INDEX 14 SCREENS
              </span>
              <h2 className="font-headline text-2xl font-bold text-[#0A0A0A]">
                DeployMate Directory
              </h2>
            </div>
            <button
              onClick={() => setMenuOpen(false)}
              className="w-8 h-8 bg-white border border-[#0A0A0A] flex items-center justify-center text-[#0A0A0A] btn-tactile"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {sessionStage !== 'authenticated' && (
            <div className="p-3 bg-red-50 border border-[#E6391E] font-mono text-xs text-[#E6391E]">
              AUTHENTICATION REQUIRED // Complete stages 01-03 to unlock internal fleet screens.
            </div>
          )}

          <div className="divide-y divide-[#0A0A0A] border border-[#0A0A0A]">
            {ALL_SCREENS.map((s) => {
              const isLocked = sessionStage !== 'authenticated' && !['splash', 'auth', 'instance_sync'].includes(s.id);
              return (
                <div
                  key={s.id}
                  onClick={() => !isLocked && navigateTo(s.id)}
                  className={`flex items-center justify-between py-3 px-4 transition-colors ${
                    isLocked
                      ? 'opacity-40 cursor-not-allowed bg-zinc-50'
                      : currentScreen === s.id
                      ? 'bg-[#0A0A0A] text-white cursor-pointer'
                      : 'bg-white text-[#0A0A0A] hover:bg-zinc-100 cursor-pointer card-tactile'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`font-mono text-xs font-bold ${
                        currentScreen === s.id ? 'text-[#E6391E]' : 'text-zinc-500'
                      }`}
                    >
                      {s.num}
                    </span>
                    <span className="font-headline text-sm font-semibold">{s.title}</span>
                  </div>
                  <span
                    className={`font-mono text-[10px] uppercase px-1.5 py-0.5 border ${
                      currentScreen === s.id
                        ? 'border-white/30 text-zinc-300'
                        : isLocked
                        ? 'border-zinc-300 text-zinc-400'
                        : 'border-[#0A0A0A] text-zinc-600'
                    }`}
                  >
                    {isLocked ? 'LOCKED' : s.category}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="pt-2">
            <button
              onClick={handleResetSession}
              className="w-full py-3 border border-[#0A0A0A] font-mono text-xs text-zinc-600 hover:bg-black hover:text-white flex items-center justify-center gap-2 btn-tactile bg-white"
            >
              <RotateCcw className="w-3.5 h-3.5 text-[#E6391E]" />
              <span>Replay Boot & Authentication Flow</span>
            </button>
          </div>
        </div>
      )}

      {/* Main Screen Content Viewport with Smooth CSS Page Transitions */}
      <main className={`flex-1 overflow-y-auto flex flex-col bg-white ${currentScreen === 'splash' ? 'p-0' : 'p-4'} ${sessionStage === 'authenticated' ? 'pb-24' : 'pb-6'}`}>
        <div key={currentScreen} className="animate-screen-enter flex-1 flex flex-col">
          {currentScreen === 'splash' && (
            <SplashScreen onContinue={handleSplashContinue} />
          )}
          {currentScreen === 'auth' && (
            <AuthScreen onAuthenticated={handleAuthenticated} />
          )}
          {currentScreen === 'instance_sync' && (
            <InstanceSyncScreen onSynced={handleSynced} />
          )}
          {currentScreen === 'overview' && overview && (
            <DashboardScreen overview={overview} onNavigate={navigateTo} />
          )}
          {currentScreen === 'model_router' && <ModelRouterScreen />}
          {currentScreen === 'departments' && (
            <DepartmentsScreen onSelectDept={() => navigateTo('tech_dept')} />
          )}
          {currentScreen === 'agent_comms' && <AgentCommsScreen />}
          {currentScreen === 'tech_dept' && (
            <TechDeptScreen
              onNavigateTriage={() => navigateTo('triage')}
              onNavigateWorktrees={() => navigateTo('worktrees')}
              onNavigateDeployments={() => navigateTo('deployments')}
            />
          )}
          {currentScreen === 'worktrees' && <WorktreesScreen />}
          {currentScreen === 'triage' && (
            <TriageQueueScreen onSelectTask={() => navigateTo('live_stream')} />
          )}
          {currentScreen === 'live_stream' && <LiveStreamScreen />}
          {currentScreen === 'deployments' && <DeploymentsScreen />}
          {currentScreen === 'projects' && <ProjectsScreen />}
          {currentScreen === 'settings' && <SettingsScreen />}
        </div>
      </main>

      {/* Bottom Sticky Locomotive Navigation (Only when Authenticated) */}
      {sessionStage === 'authenticated' && (
        <nav className="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-white/95 backdrop-blur border-t border-[#0A0A0A] px-3 pt-2 pb-[max(env(safe-area-inset-bottom),0.75rem)] flex items-center justify-around z-30">
          <button
            onClick={() => navigateTo('overview')}
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile ${
              currentScreen === 'overview'
                ? 'text-[#E6391E] font-bold'
                : 'text-zinc-500 hover:text-[#0A0A0A]'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Radar</span>
          </button>

          <button
            onClick={() => navigateTo('triage')}
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile ${
              currentScreen === 'triage'
                ? 'text-[#E6391E] font-bold'
                : 'text-zinc-500 hover:text-[#0A0A0A]'
            }`}
          >
            <Inbox className="w-4 h-4" />
            <span>Triage</span>
          </button>

          <button
            onClick={() => navigateTo('worktrees')}
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile ${
              currentScreen === 'worktrees'
                ? 'text-[#E6391E] font-bold'
                : 'text-zinc-500 hover:text-[#0A0A0A]'
            }`}
          >
            <GitBranch className="w-4 h-4" />
            <span>Git</span>
          </button>

          <button
            onClick={() => navigateTo('model_router')}
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile ${
              currentScreen === 'model_router'
                ? 'text-[#E6391E] font-bold'
                : 'text-zinc-500 hover:text-[#0A0A0A]'
            }`}
          >
            <Cpu className="w-4 h-4" />
            <span>Quotas</span>
          </button>

          <button
            onClick={() => navigateTo('live_stream')}
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile ${
              currentScreen === 'live_stream'
                ? 'text-[#E6391E] font-bold'
                : 'text-zinc-500 hover:text-[#0A0A0A]'
            }`}
          >
            <Terminal className="w-4 h-4" />
            <span>Logs</span>
          </button>

          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile ${
              menuOpen
                ? 'text-[#E6391E] font-bold'
                : 'text-zinc-500 hover:text-[#0A0A0A]'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>14 Screens</span>
          </button>
        </nav>
      )}
    </div>
  );
}
