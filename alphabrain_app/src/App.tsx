import React, { useState, useEffect } from 'react';
import { ScreenId, ExecutiveOverview } from './types';
import { mobileApi } from './api/client';
import {
  LayoutDashboard,
  Inbox,
  Mic,
  GitPullRequest,
  Menu,
  X,
  Smartphone,
  ShieldAlert,
  Server,
  Activity,
  Sliders,
  Database,
  Lock,
  FileCode,
  Layers,
} from 'lucide-react';

import { DashboardScreen } from './screens/DashboardScreen';
import { TriageQueueScreen } from './screens/TriageQueueScreen';
import { TaskDetailScreen } from './screens/TaskDetailScreen';
import { CodeDiffScreen } from './screens/CodeDiffScreen';
import { VoiceBriefingScreen } from './screens/VoiceBriefingScreen';
import { SprintFleetScreen } from './screens/SprintFleetScreen';
import { PrPromotionScreen } from './screens/PrPromotionScreen';
import { DeploymentsScreen } from './screens/DeploymentsScreen';
import { SelfHealingScreen } from './screens/SelfHealingScreen';
import { HardwareTelemetryScreen } from './screens/HardwareTelemetryScreen';
import { PrivacyComplianceScreen } from './screens/PrivacyComplianceScreen';
import { ModelRouterScreen } from './screens/ModelRouterScreen';
import { AuditTrailScreen } from './screens/AuditTrailScreen';
import { EmergencyStopScreen } from './screens/EmergencyStopScreen';

const ALL_SCREENS: Array<{ id: ScreenId; num: string; title: string; category: string }> = [
  { id: 'overview', num: '01', title: 'Mission Control', category: 'Executive' },
  { id: 'triage', num: '02', title: 'Triage Queue', category: 'Intake' },
  { id: 'task_detail', num: '03', title: 'Spec Reviewer', category: 'Worktree' },
  { id: 'code_diff', num: '04', title: 'Interactive Diff', category: 'Git' },
  { id: 'voice_briefing', num: '05', title: 'Eva Voice CTO', category: 'Audio' },
  { id: 'sprint_fleet', num: '06', title: 'Autonomous Fleet', category: 'Swarm' },
  { id: 'pr_promotion', num: '07', title: 'One-Tap PR Merge', category: 'Release' },
  { id: 'deployments', num: '08', title: 'Multi-Cloud', category: 'Deploy' },
  { id: 'self_healing', num: '09', title: 'CI/CD Healing', category: 'Resilience' },
  { id: 'hardware_telemetry', num: '10', title: 'Hardware Sensors', category: 'Hardware' },
  { id: 'privacy_compliance', num: '11', title: 'P13.1 Privacy', category: 'Security' },
  { id: 'model_router', num: '12', title: 'OC-EDS Router', category: 'Models' },
  { id: 'audit_trail', num: '13', title: 'Audit Ledger', category: 'Audit' },
  { id: 'emergency_stop', num: '14', title: 'Emergency Switch', category: 'Founder' },
];

export function App() {
  const [currentScreen, setCurrentScreen] = useState<ScreenId>('overview');
  const [selectedTaskId, setSelectedTaskId] = useState<string>('tsk_eva_1d262851bd6a');
  const [menuOpen, setMenuOpen] = useState(false);
  const [overview, setOverview] = useState<ExecutiveOverview | null>(null);

  useEffect(() => {
    mobileApi.getOverview().then(setOverview).catch(console.error);
  }, [currentScreen]);

  const navigateTo = (screen: ScreenId) => {
    setCurrentScreen(screen);
    setMenuOpen(false);
  };

  const handleSelectTask = (taskId: string) => {
    setSelectedTaskId(taskId);
    setCurrentScreen('task_detail');
  };

  const handleViewDiff = (taskId: string) => {
    setSelectedTaskId(taskId);
    setCurrentScreen('code_diff');
  };

  const handlePromote = (taskId: string) => {
    setSelectedTaskId(taskId);
    setCurrentScreen('pr_promotion');
  };

  return (
    <div className="min-h-screen bg-background text-slate-100 flex flex-col font-sans max-w-md mx-auto relative shadow-2xl border-x border-card-border/40">
      {/* Top Header Bar */}
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur border-b border-card-border px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-accent flex items-center justify-center font-display font-bold text-white text-xs">
            AB
          </div>
          <div>
            <div className="font-display font-bold text-sm tracking-tight leading-none text-white">
              AlphaBrain Companion
            </div>
            <div className="font-mono text-[10px] text-muted tracking-widest mt-0.5 uppercase">
              DeployMate Locomotive
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="font-mono text-[11px] text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-2 py-0.5 rounded flex items-center gap-1">
            <Smartphone className="w-3 h-3" />
            <span>10BF5P2AZF0010T</span>
          </div>

          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="w-8 h-8 rounded bg-card border border-card-border flex items-center justify-center text-slate-300 hover:text-white"
          >
            {menuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </header>

      {/* Screen Drawer Overlay */}
      {menuOpen && (
        <div className="absolute inset-0 z-50 bg-background/98 backdrop-blur p-5 overflow-y-auto space-y-4">
          <div className="flex items-center justify-between border-b border-card-border pb-3">
            <div>
              <span className="font-mono text-xs text-accent">INDEX 14 SCREENS</span>
              <h2 className="font-display text-xl font-bold text-white">DeployMate Directory</h2>
            </div>
            <button
              onClick={() => setMenuOpen(false)}
              className="w-8 h-8 rounded bg-card border border-card-border flex items-center justify-center text-slate-300"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-1">
            {ALL_SCREENS.map((s) => (
              <div
                key={s.id}
                onClick={() => navigateTo(s.id)}
                className={`locomotive-row flex items-center justify-between py-2.5 px-3 rounded-lg cursor-pointer ${
                  currentScreen === s.id ? 'bg-accent/10 border-accent text-accent' : 'text-slate-300'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-accent font-bold">{s.num}</span>
                  <span className="font-display text-sm font-semibold">{s.title}</span>
                </div>
                <span className="font-mono text-[10px] text-muted uppercase bg-card px-2 py-0.5 rounded border border-card-border">
                  {s.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Screen Content Viewport */}
      <main className="flex-1 p-4 pb-24 overflow-y-auto">
        {currentScreen === 'overview' && overview && (
          <DashboardScreen overview={overview} onNavigate={navigateTo} />
        )}
        {currentScreen === 'triage' && (
          <TriageQueueScreen onSelectTask={handleSelectTask} />
        )}
        {currentScreen === 'task_detail' && (
          <TaskDetailScreen
            taskId={selectedTaskId}
            onBack={() => setCurrentScreen('triage')}
            onViewDiff={handleViewDiff}
          />
        )}
        {currentScreen === 'code_diff' && (
          <CodeDiffScreen
            taskId={selectedTaskId}
            onBack={() => setCurrentScreen('task_detail')}
            onPromote={handlePromote}
          />
        )}
        {currentScreen === 'voice_briefing' && <VoiceBriefingScreen />}
        {currentScreen === 'sprint_fleet' && <SprintFleetScreen />}
        {currentScreen === 'pr_promotion' && <PrPromotionScreen />}
        {currentScreen === 'deployments' && <DeploymentsScreen />}
        {currentScreen === 'self_healing' && <SelfHealingScreen />}
        {currentScreen === 'hardware_telemetry' && <HardwareTelemetryScreen />}
        {currentScreen === 'privacy_compliance' && <PrivacyComplianceScreen />}
        {currentScreen === 'model_router' && <ModelRouterScreen />}
        {currentScreen === 'audit_trail' && <AuditTrailScreen />}
        {currentScreen === 'emergency_stop' && <EmergencyStopScreen />}
      </main>

      {/* Bottom Sticky Locomotive Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-card/95 backdrop-blur border-t border-card-border px-3 py-2 flex items-center justify-around z-30">
        <button
          onClick={() => navigateTo('overview')}
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
            currentScreen === 'overview' ? 'text-accent' : 'text-muted hover:text-slate-200'
          }`}
        >
          <LayoutDashboard className="w-4 h-4" />
          <span>Radar</span>
        </button>

        <button
          onClick={() => navigateTo('triage')}
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
            currentScreen === 'triage' ? 'text-accent' : 'text-muted hover:text-slate-200'
          }`}
        >
          <Inbox className="w-4 h-4" />
          <span>Triage</span>
        </button>

        <button
          onClick={() => navigateTo('voice_briefing')}
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
            currentScreen === 'voice_briefing' ? 'text-accent' : 'text-muted hover:text-slate-200'
          }`}
        >
          <Mic className="w-4 h-4" />
          <span>Eva Voice</span>
        </button>

        <button
          onClick={() => navigateTo('pr_promotion')}
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
            currentScreen === 'pr_promotion' ? 'text-accent' : 'text-muted hover:text-slate-200'
          }`}
        >
          <GitPullRequest className="w-4 h-4" />
          <span>Merge PR</span>
        </button>

        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className={`flex flex-col items-center gap-1 font-mono text-[10px] ${
            menuOpen ? 'text-accent' : 'text-muted hover:text-slate-200'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>14 Screens</span>
        </button>
      </nav>
    </div>
  );
}
