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
} from 'lucide-react';

import { SplashScreen } from './screens/SplashScreen';
import { AuthScreen } from './screens/AuthScreen';
import { EnrollmentScreen } from './screens/EnrollmentScreen';
import { InstanceSyncScreen } from './screens/InstanceSyncScreen';
import { QRProvisioningScreen, SASVerificationScreen } from './screens/QRProvisioningScreen';
import { EvaMeetingScreen } from './screens/EvaMeetingScreen';
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
  { id: 'splash', num: '01', title: 'Splash Screen', category: 'Brand' },
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
  { id: 'deployments', num: '12', title: 'Vercel Console', category: 'Deploy' },
  { id: 'projects', num: '13', title: 'Project Portfolio', category: 'Portfolio' },
  { id: 'settings', num: '14', title: 'Global Settings', category: 'Founder' },
  { id: 'eva_meeting', num: '15', title: 'Eva Meeting', category: 'Telephony' },
];

export function App() {
  const [currentScreen, setCurrentScreen] = useState<ScreenId>('overview');
  const [menuOpen, setMenuOpen] = useState(false);
  const [overview, setOverview] = useState<ExecutiveOverview | null>(null);

  useEffect(() => {
    mobileApi
      .getOverview()
      .then(setOverview)
      .catch((err) => {
        console.warn('Backend overview fetch warning (using fallback state):', err);
        setOverview({
          app_version: '1.0.0',
          system_status: 'HEALTHY',
          emergency_stop: {
            active: false,
            locked_at: null,
            lock_file: '',
            reason: '',
            triggered_by: '',
          },
          telemetry: {
            host_cpu_percent: 18.4,
            host_ram_percent: 42.1,
            host_ram_used_gb: 6.7,
            host_ram_total_gb: 16.0,
            thermal_pressure: 'nominal',
            battery_level_percent: 94,
            battery_charging: true,
            usb_device_connected: true,
            usb_device_serial: '10BF5P2AZF0010T',
            usb_device_name: 'Android Device',
          },
          triage_backlog_count: 1,
          active_sprint_workers: 4,
          recent_deployments_count: 3,
          eva_status: 'READY',
        });
      });
  }, [currentScreen]);

  const navigateTo = (screen: ScreenId) => {
    setCurrentScreen(screen);
    setMenuOpen(false);
  };

  return (
    <div className="min-h-screen bg-white text-[#0A0A0A] flex flex-col font-sans max-w-md mx-auto relative border-x border-[#0A0A0A] selection:bg-[#E6391E] selection:text-white">
      {/* Top Header Bar with Safe-Area Notch Inset */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-[#0A0A0A] px-4 pt-[max(env(safe-area-inset-top),2.5rem)] pb-3 flex items-center justify-between">
        <div
          onClick={() => navigateTo('splash')}
          className="flex items-center gap-2.5 cursor-pointer"
        >
          <div className="w-7 h-7 bg-[#0A0A0A] flex items-center justify-center font-headline font-bold text-white text-xs">
            <span className="text-[#E6391E] font-mono mr-0.5">α</span>B
          </div>
          <div>
            <div className="font-headline font-bold text-sm tracking-tight leading-none text-[#0A0A0A]">
              AlphaBrain
            </div>
            <div className="font-mono text-[9px] text-zinc-500 tracking-widest mt-0.5 uppercase">
              DeployMate Locomotive
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="font-mono text-[10px] text-[#0A0A0A] bg-zinc-100 border border-[#0A0A0A] px-2 py-0.5 flex items-center gap-1">
            <Smartphone className="w-3 h-3 text-[#E6391E]" />
            <span className="font-semibold">10BF5P2AZF0010T</span>
          </div>

          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="w-8 h-8 bg-white border border-[#0A0A0A] flex items-center justify-center text-[#0A0A0A] hover:bg-zinc-100 transition-colors"
          >
            {menuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </header>

      {/* Screen Drawer Overlay (14-Screen Locomotive Directory) */}
      {menuOpen && (
        <div className="absolute inset-0 z-50 bg-white/98 backdrop-blur p-5 pt-[max(env(safe-area-inset-top),2.5rem)] overflow-y-auto space-y-4">
          <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-3">
            <div>
              <span className="font-mono text-xs text-[#E6391E] font-bold">
                INDEX {ALL_SCREENS.length} SCREENS
              </span>
              <h2 className="font-headline text-2xl font-bold text-[#0A0A0A]">
                DeployMate Directory
              </h2>
            </div>
            <button
              onClick={() => setMenuOpen(false)}
              className="w-8 h-8 bg-white border border-[#0A0A0A] flex items-center justify-center text-[#0A0A0A]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="divide-y divide-[#0A0A0A] border border-[#0A0A0A]">
            {ALL_SCREENS.map((s) => (
              <div
                key={s.id}
                onClick={() => navigateTo(s.id)}
                className={`flex items-center justify-between py-3 px-4 cursor-pointer transition-colors ${
                  currentScreen === s.id
                    ? 'bg-[#0A0A0A] text-white'
                    : 'bg-white text-[#0A0A0A] hover:bg-zinc-100'
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
                      : 'border-[#0A0A0A] text-zinc-600'
                  }`}
                >
                  {s.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Screen Content Viewport */}
      <main className="flex-1 p-4 pb-24 overflow-y-auto flex flex-col bg-white">
        {currentScreen === 'splash' && (
          <SplashScreen onContinue={() => navigateTo('overview')} />
        )}
        {currentScreen === 'enrollment' && (
          <EnrollmentScreen
            onCompleted={() => navigateTo('auth')}
            onCancel={() => navigateTo('auth')}
          />
        )}
        {currentScreen === 'auth' && (
          <AuthScreen
            onAuthenticated={() => navigateTo('overview')}
            onNavigateEnroll={() => navigateTo('enrollment')}
          />
        )}
        {currentScreen === 'instance_sync' && (
          <InstanceSyncScreen onSynced={() => navigateTo('overview')} />
        )}
        {currentScreen === 'qr_provisioning' && (
          <QRProvisioningScreen
            onSynced={() => navigateTo('overview')}
            onNavigateSAS={() => navigateTo('sas_verification')}
          />
        )}
        {currentScreen === 'sas_verification' && (
          <SASVerificationScreen
            onVerified={() => navigateTo('overview')}
            onNavigateQR={() => navigateTo('qr_provisioning')}
          />
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
        {currentScreen === 'eva_meeting' && (
          <EvaMeetingScreen onLeave={() => navigateTo('overview')} />
        )}
      </main>

      {/* Bottom Sticky Locomotive Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-white/95 backdrop-blur border-t border-[#0A0A0A] px-3 pt-2 pb-[max(env(safe-area-inset-bottom),0.75rem)] flex items-center justify-around z-30">
        <button
          onClick={() => navigateTo('overview')}
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
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
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
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
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
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
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
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
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
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
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
            menuOpen
              ? 'text-[#E6391E] font-bold'
              : 'text-zinc-500 hover:text-[#0A0A0A]'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>{ALL_SCREENS.length} Screens</span>
        </button>
      </nav>
    </div>
  );
}
