import React, { useState, useEffect } from 'react';
import { ScreenId, ExecutiveOverview, DashboardScreenData } from './types';
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
import { QRProvisioningScreen, SASVerificationScreen } from './screens/QRProvisioningScreen';
import { EvaMeetingScreen } from './screens/EvaMeetingScreen';
import { DashboardScreen } from './screens/DashboardScreen';
import { ModelRouterScreen } from './screens/ModelRouterScreen';
import { DepartmentsScreen } from './screens/DepartmentsScreen';
import { AgentCommsScreen } from './screens/AgentCommsScreen';
import { TechDeptScreen } from './screens/TechDeptScreen';
import { EnvVaultScreen } from './screens/EnvVaultScreen';
import { WorktreesScreen } from './screens/WorktreesScreen';
import { TriageQueueScreen } from './screens/TriageQueueScreen';
import { LiveStreamScreen } from './screens/LiveStreamScreen';
import { DeploymentsScreen } from './screens/DeploymentsScreen';
import { ProjectsScreen } from './screens/ProjectsScreen';
import { SettingsScreen } from './screens/SettingsScreen';
import { LoadingSpinner } from './components/ui/LoadingSpinner';
import { SkeletonCard, SkeletonList } from './components/ui/Skeleton';

type SessionStage = 'splash' | 'auth' | 'instance_sync' | 'authenticated';

const ALL_SCREENS: Array<{ id: ScreenId; num: string; title: string; category: string }> = [
  { id: 'splash', num: '01', title: 'Splash Screen', category: 'Brand' },
  { id: 'auth', num: '02', title: 'Founder Access', category: 'Security' },
  { id: 'instance_sync', num: '03', title: 'Instance Sync', category: 'Hardware' },
  { id: 'overview', num: '04', title: 'Command Center', category: 'Mission' },
  { id: 'model_router', num: '05', title: 'AI Quotas', category: 'Models' },
  { id: 'departments', num: '06', title: 'Departments', category: 'Structure' },
  { id: 'agent_comms', num: '07', title: 'Agent Comms', category: 'Mesh' },
  { id: 'env_vault', num: '08', title: '.env Secrets Vault', category: 'Security' },
  { id: 'worktrees', num: '09', title: 'Worktrees', category: 'Git' },
  { id: 'triage', num: '10', title: 'Triage Board', category: 'Intake' },
  { id: 'live_stream', num: '11', title: 'Live Stream', category: 'Logs' },
  { id: 'deployments', num: '12', title: 'Vercel Console', category: 'Deploy' },
  { id: 'projects', num: '13', title: 'Delivery Board', category: 'Delivery' },
  { id: 'settings', num: '14', title: 'Global Settings', category: 'Founder' },
  { id: 'eva_meeting', num: '15', title: 'Eva Meeting', category: 'Telephony' },
];

export function App() {
  const [sessionStage, setSessionStage] = useState<SessionStage>(() => {
    try {
      const saved = sessionStorage.getItem('alphabrain_session_token');
      return saved ? 'authenticated' : 'splash';
    } catch {
      return 'splash';
    }
  });

  const [currentScreen, setCurrentScreen] = useState<ScreenId>(() => {
    try {
      const saved = sessionStorage.getItem('alphabrain_session_token');
      return saved ? 'overview' : 'splash';
    } catch {
      return 'splash';
    }
  });

  const [menuOpen, setMenuOpen] = useState(false);
  const [overview, setOverview] = useState<ExecutiveOverview | null>(null);
  const [dashboardData, setDashboardData] = useState<DashboardScreenData | null>(null);

  useEffect(() => {
    if (sessionStage !== 'authenticated') return;

    mobileApi
      .getDashboard()
      .then(setDashboardData)
      .catch((err) => console.warn('Dashboard fetch warning:', err));

    mobileApi
      .getOverview()
      .then(setOverview)
      .catch((err) => {
        console.warn('Backend overview fetch warning (using honest OFFLINE state):', err);
        setOverview({
          app_version: '1.0.0',
          system_status: 'OFFLINE',
          emergency_stop: {
            active: false,
            locked_at: null,
            lock_file: '',
            reason: 'Backend offline • connection refused',
            triggered_by: '',
          },
          telemetry: {
            host_cpu_percent: 0,
            host_ram_percent: 0,
            host_ram_used_gb: 0,
            host_ram_total_gb: 0,
            thermal_pressure: 'offline',
            battery_level_percent: 0,
            battery_charging: false,
            usb_device_connected: false,
            usb_device_serial: 'DISCONNECTED',
            usb_device_name: 'None',
          },
          triage_backlog_count: 0,
          active_sprint_workers: 0,
          recent_deployments_count: 0,
          eva_status: 'OFFLINE',
        });
      });
  }, [currentScreen, sessionStage]);

  const handleSplashContinue = () => {
    // First-time onboarding sequence: Set Master PIN -> Connect Instance
    const hasExistingPin = Boolean(localStorage.getItem('alphabrain_master_pin_hash'));
    if (hasExistingPin) {
      setSessionStage('auth');
      setCurrentScreen('auth');
    } else {
      setSessionStage('auth');
      setCurrentScreen('enrollment');
    }
  };

  const handleAuthenticated = () => {
    setSessionStage('instance_sync');
    setCurrentScreen('instance_sync');
  };

  const handleSynced = () => {
    setSessionStage('authenticated');
    setCurrentScreen('overview');
    try {
      sessionStorage.setItem('alphabrain_session_token', 'active_founder_session');
    } catch {
      // Ignore storage restrictions in sandboxed runs
    }
  };

  const navigateTo = (screen: ScreenId) => {
    // Before authentication, only access gate screens are permitted
    if (sessionStage !== 'authenticated') {
      const allowedPreAuth: ScreenId[] = [
        'splash',
        'auth',
        'enrollment',
        'instance_sync',
        'qr_provisioning',
        'sas_verification',
      ];
      if (allowedPreAuth.includes(screen)) {
        setCurrentScreen(screen);
      } else {
        setCurrentScreen('auth');
      }
      setMenuOpen(false);
      return;
    }

    setCurrentScreen(screen);
    setMenuOpen(false);
  };

  return (
    <div
      className={`min-h-screen ${
        currentScreen === 'eva_meeting' ? 'h-screen h-[100dvh] overflow-hidden' : ''
      } bg-white text-[#0A0A0A] flex flex-col font-sans max-w-md mx-auto relative border-x border-[#0A0A0A] selection:bg-[#E6391E] selection:text-white`}
    >
      {/* Top Header Bar with Safe-Area Notch Inset (Hidden on Splash and Eva Meeting) */}
      {currentScreen !== 'splash' && currentScreen !== 'eva_meeting' && (
        <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-[#0A0A0A] px-4 pt-[max(env(safe-area-inset-top),2.5rem)] pb-3 flex items-center justify-between">
          <div
            onClick={() => navigateTo('splash')}
            className="flex items-center gap-2.5 cursor-pointer"
          >
            <img
              src="/alphabrain_logo.svg"
              alt="AlphaBrain Logo"
              className="w-7 h-7 object-contain"
            />
            <div className="font-headline font-bold text-base tracking-tight leading-none text-[#0A0A0A]">
              AlphaBrain
            </div>
          </div>

          <div className="flex items-center gap-2">
            {sessionStage === 'authenticated' && (
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="w-8 h-8 bg-white border border-[#0A0A0A] flex items-center justify-center text-[#0A0A0A] hover:bg-zinc-100 transition-colors"
              >
                {menuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
              </button>
            )}
          </div>
        </header>
      )}

      {/* Screen Drawer Overlay (Only when Authenticated) */}
      {menuOpen && sessionStage === 'authenticated' && (
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

      {/* Main Screen Content Viewport with Proper Padding */}
      <main
        className={`flex-1 flex flex-col ${
          currentScreen === 'eva_meeting'
            ? 'p-0 pb-0 bg-white h-full overflow-hidden'
            : currentScreen === 'splash'
            ? 'p-0 bg-white overflow-y-auto'
            : 'p-4 bg-white overflow-y-auto'
        } ${
          currentScreen === 'eva_meeting'
            ? 'pb-0'
            : sessionStage === 'authenticated'
            ? 'pb-24'
            : 'pb-[max(env(safe-area-inset-bottom),2.5rem)]'
        }`}
      >
        {currentScreen === 'splash' && (
          <SplashScreen onContinue={handleSplashContinue} />
        )}
        {currentScreen === 'enrollment' && (
          <EnrollmentScreen
            onCompleted={() => setCurrentScreen('instance_sync')}
            onCancel={() => setCurrentScreen('splash')}
          />
        )}
        {currentScreen === 'auth' && (
          <AuthScreen
            onAuthenticated={handleAuthenticated}
            onNavigateEnroll={() => setCurrentScreen('enrollment')}
          />
        )}
        {currentScreen === 'instance_sync' && (
          <QRProvisioningScreen
            onSynced={handleSynced}
            onNavigateSAS={() => setCurrentScreen('sas_verification')}
          />
        )}
        {currentScreen === 'qr_provisioning' && (
          <QRProvisioningScreen
            onSynced={handleSynced}
            onNavigateSAS={() => setCurrentScreen('sas_verification')}
          />
        )}
        {currentScreen === 'sas_verification' && (
          <SASVerificationScreen
            onVerified={handleSynced}
            onNavigateQR={() => setCurrentScreen('qr_provisioning')}
          />
        )}
        {currentScreen === 'overview' && overview && (
          <DashboardScreen overview={overview} dashboardData={dashboardData} onNavigate={navigateTo} />
        )}
        {currentScreen === 'overview' && !overview && (
          <div className="space-y-4 animate-screen-enter">
            <div className="p-4 border border-[#0A0A0A] bg-zinc-50 flex items-center justify-center">
              <LoadingSpinner size="md" label="Initializing Mission Kernel..." />
            </div>
            <SkeletonCard />
            <SkeletonList rows={4} />
          </div>
        )}
        {currentScreen === 'model_router' && <ModelRouterScreen />}
        {currentScreen === 'departments' && (
          <DepartmentsScreen onSelectDept={(screen) => navigateTo(screen)} />
        )}
        {currentScreen === 'env_vault' && <EnvVaultScreen />}
        {currentScreen === 'agent_comms' && (
          <AgentCommsScreen onNavigateEva={() => navigateTo('eva_meeting')} />
        )}
        {currentScreen === 'tech_dept' && (
          <TechDeptScreen
            onNavigateTriage={() => navigateTo('triage')}
            onNavigateWorktrees={() => navigateTo('worktrees')}
            onNavigateDeployments={() => navigateTo('deployments')}
          />
        )}
        {currentScreen === 'worktrees' && (
          <WorktreesScreen onNavigateToTask={() => navigateTo('triage')} />
        )}
        {currentScreen === 'triage' && (
          <TriageQueueScreen onSelectTask={() => navigateTo('live_stream')} />
        )}
        {currentScreen === 'live_stream' && <LiveStreamScreen />}
        {currentScreen === 'deployments' && <DeploymentsScreen />}
        {currentScreen === 'projects' && <ProjectsScreen />}
        {currentScreen === 'settings' && (
          <SettingsScreen onNavigateToScreen={(s) => navigateTo(s as ScreenId)} />
        )}
        {currentScreen === 'eva_meeting' && (
          <EvaMeetingScreen onLeave={() => navigateTo('overview')} />
        )}
      </main>

      {/* Bottom Sticky Locomotive Navigation (Only when Authenticated and Not on Eva Meeting) */}
      {sessionStage === 'authenticated' && currentScreen !== 'eva_meeting' && (
        <nav className="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-white/95 backdrop-blur border-t border-[#0A0A0A] px-3 pt-2 pb-[max(env(safe-area-inset-bottom),0.75rem)] flex items-center justify-around z-30">
          <button
            onClick={() => navigateTo('overview')}
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile hover-lift transition-smooth ${
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
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile hover-lift transition-smooth ${
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
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile hover-lift transition-smooth ${
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
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile hover-lift transition-smooth ${
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
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile hover-lift transition-smooth ${
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
            className={`flex flex-col items-center gap-1 font-mono text-[10px] btn-tactile hover-lift transition-smooth ${
              menuOpen
                ? 'text-[#E6391E] font-bold'
                : 'text-zinc-500 hover:text-[#0A0A0A]'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>{ALL_SCREENS.length} Screens</span>
          </button>
        </nav>
      )}
    </div>
  );
}
