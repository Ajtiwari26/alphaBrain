import React, { useState } from 'react';
import { ScreenId } from './types';
import { M01_NodeSetup } from './screens/M01_NodeSetup';
import { M02_PairingStation } from './screens/M02_PairingStation';
import { M03_CommandNode } from './screens/M03_CommandNode';
import { M04_SecurityEnclave } from './screens/M04_SecurityEnclave';
import { M05_MeetingSetup } from './screens/M05_MeetingSetup';
import { EvaMeetingScreen } from './screens/EvaMeetingScreen';
import { ProjectsScreen } from './screens/ProjectsScreen';
import { ModelRouterScreen } from './screens/ModelRouterScreen';
import { TriageQueueScreen } from './screens/TriageQueueScreen';
import { DepartmentsScreen } from './screens/DepartmentsScreen';
import { EmergencyStopScreen } from './screens/EmergencyStopScreen';
import {
  LayoutGrid,
  QrCode,
  Terminal,
  Shield,
  Radio,
  PhoneCall,
  FolderGit2,
  Cpu,
  ListTodo,
  Building2,
  AlertOctagon,
} from 'lucide-react';

export const App: React.FC = () => {
  const [currentScreen, setCurrentScreen] = useState<ScreenId>('M01_NodeSetup');

  const navItems: { id: ScreenId; label: string; code: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'M01_NodeSetup', label: 'Node Setup', code: 'M-01', icon: LayoutGrid },
    { id: 'M02_PairingStation', label: 'Pairing', code: 'M-02', icon: QrCode },
    { id: 'M03_CommandNode', label: 'Command Node', code: 'M-03', icon: Terminal },
    { id: 'M04_SecurityEnclave', label: 'Security', code: 'M-04', icon: Shield },
    { id: 'EvaMeeting', label: 'Eva Live', code: 'MC-07', icon: PhoneCall },
    { id: 'Projects', label: 'Projects', code: 'PORT', icon: FolderGit2 },
    { id: 'ModelRouter', label: 'AI Quotas', code: 'OC-EDS', icon: Cpu },
    { id: 'TriageQueue', label: 'Triage', code: 'QUEUE', icon: ListTodo },
    { id: 'Departments', label: 'Depts', code: 'CORP', icon: Building2 },
    { id: 'EmergencyStop', label: 'Kill Switch', code: 'HALT', icon: AlertOctagon },
  ];

  return (
    <div className="min-h-screen bg-white text-[#0A0A0A] flex flex-col font-sans selection:bg-[#E6391E] selection:text-white">
      {/* Top Application Bar */}
      <header className="border-b border-[#0A0A0A] bg-white sticky top-0 z-50">
        <div className="w-full px-6 h-14 flex items-center justify-between">
          {/* Brand Mark */}
          <div className="flex items-center gap-3 shrink-0 mr-4">
            <img
              src="/alphabrain_logo.svg"
              alt="AlphaBrain Logo"
              className="w-7 h-7 object-contain"
            />
            <div className="flex items-baseline gap-2">
              <span className="font-mono font-bold tracking-tight text-sm uppercase">
                AlphaBrain
              </span>
              <span className="hidden md:inline text-[11px] font-mono text-neutral-500 uppercase tracking-widest">
                Command Node v2.0 (macOS)
              </span>
            </div>
          </div>

          {/* Symmetrical Parity Quick Links / Status */}
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-neutral-50 border border-[#0A0A0A] font-mono text-xs">
              <span className="text-neutral-500">ENGINE:</span>
              <img
                src="/deploymate_logo.svg"
                alt="DeployMate"
                className="h-3.5 object-contain"
              />
            </div>
            <div className="flex items-center gap-1.5 font-mono text-xs border-l border-[#0A0A0A] pl-4">
              <Radio className="w-3.5 h-3.5 text-emerald-600 animate-pulse" />
              <span className="font-bold">CLOUD SYNCED</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main macOS Application Frame with Left Sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Mac App Sidebar */}
        <aside className="w-72 border-r border-[#0A0A0A] bg-neutral-50/70 flex flex-col justify-between shrink-0 select-none overflow-y-auto">
          {/* Sidebar Top: Prominent Co-Branding Banner */}
          <div className="p-4 border-b border-[#0A0A0A] bg-white space-y-3">
            <div className="flex items-center gap-3">
              <img
                src="/alphabrain_logo.svg"
                alt="AlphaBrain Logo"
                className="w-8 h-8 object-contain"
              />
              <div>
                <div className="font-mono font-bold text-sm tracking-tight text-[#0A0A0A] uppercase">
                  AlphaBrain
                </div>
                <div className="font-mono text-[10px] text-neutral-400 uppercase tracking-wider">
                  Mac Command Node
                </div>
              </div>
            </div>

            {/* Co-Branding Callout */}
            <div className="border border-[#0A0A0A] bg-neutral-50 p-3 space-y-2">
              <div className="font-mono text-[11px] font-bold text-[#0A0A0A] tracking-tight">
                AlphaBrain is powered by DeployMate
              </div>
              <div className="flex items-center gap-2 pt-1 border-t border-neutral-200">
                <span className="font-mono text-[9px] text-neutral-500 uppercase tracking-widest">
                  ENGINE
                </span>
                <img
                  src="/deploymate_logo.svg"
                  alt="DeployMate"
                  className="h-4 object-contain"
                />
              </div>
            </div>
          </div>

          {/* Sidebar Navigation Items */}
          <nav className="flex-1 p-3 space-y-1 font-mono text-xs overflow-y-auto">
            <div className="px-2 py-1 text-[10px] text-neutral-400 uppercase tracking-wider">
              Workspaces & Nodes
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentScreen === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentScreen(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 border transition-all text-left btn-tactile ${
                    isActive
                      ? 'bg-[#0A0A0A] text-white border-[#0A0A0A] font-bold shadow-sm'
                      : 'bg-white text-neutral-700 border-neutral-200 hover:border-[#0A0A0A] hover:bg-neutral-100'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-[#E6391E]' : 'text-neutral-500'}`} />
                    <span className="tracking-wide text-[12px]">{item.label}</span>
                  </div>
                  <span
                    className={`text-[9px] uppercase px-1.5 py-0.5 font-mono ${
                      isActive ? 'bg-[#E6391E] text-white' : 'bg-neutral-100 text-neutral-500'
                    }`}
                  >
                    {item.code}
                  </span>
                </button>
              );
            })}
          </nav>

          {/* Sidebar Bottom: Co-Branding Status Enclave */}
          <div className="p-4 border-t border-[#0A0A0A] bg-white space-y-2.5">
            <div className="flex items-center justify-between font-mono text-[10px]">
              <span className="text-neutral-400 uppercase tracking-widest">ECOSYSTEM</span>
              <span className="text-emerald-700 font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                ACTIVE
              </span>
            </div>
            <div className="flex items-center justify-between gap-2 p-2 bg-neutral-50 border border-neutral-200">
              <img
                src="/alphabrain_logo.svg"
                alt="AlphaBrain Logo"
                className="w-6 h-6 object-contain"
              />
              <span className="font-mono text-xs text-neutral-400 font-bold">+</span>
              <img
                src="/deploymate_logo.svg"
                alt="DeployMate Logo"
                className="h-4 object-contain"
              />
            </div>
            <div className="font-mono text-[10px] text-neutral-600 text-center">
              AlphaBrain is powered by DeployMate
            </div>
          </div>
        </aside>

        {/* Main Screen Content View */}
        <main className="flex-1 overflow-y-auto bg-white transition-smooth">
          {currentScreen === 'M01_NodeSetup' && <M01_NodeSetup onNavigate={setCurrentScreen} />}
          {currentScreen === 'M02_PairingStation' && <M02_PairingStation onNavigate={setCurrentScreen} />}
          {currentScreen === 'M03_CommandNode' && <M03_CommandNode onNavigate={setCurrentScreen} />}
          {currentScreen === 'M04_SecurityEnclave' && <M04_SecurityEnclave onNavigate={setCurrentScreen} />}
          {currentScreen === 'EvaMeeting' && <EvaMeetingScreen onLeave={() => setCurrentScreen('M03_CommandNode')} />}
          {currentScreen === 'Projects' && <ProjectsScreen />}
          {currentScreen === 'ModelRouter' && <ModelRouterScreen />}
          {currentScreen === 'TriageQueue' && <TriageQueueScreen onSelectTask={(id) => console.log('Selected task:', id)} />}
          {currentScreen === 'Departments' && <DepartmentsScreen onSelectDept={(d) => console.log('Selected dept:', d)} />}
          {currentScreen === 'EmergencyStop' && <EmergencyStopScreen />}
        </main>
      </div>

      {/* Bottom Status Bar */}
      <footer className="border-t border-[#0A0A0A] bg-neutral-50 py-2 px-6 font-mono text-[11px] text-neutral-600 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <span>HOST: <strong className="text-black">Apple M4 Max (macOS 15)</strong></span>
          <span>BRANCH: <strong className="text-[#E6391E]">alpha/tsk_eva_9449f52da6e2</strong></span>
          <span>CORE: <strong className="text-black">Tauri 2.0 (Rust) + React 19</strong></span>
        </div>
        <div className="flex items-center gap-3">
          <span>API: <strong className="text-emerald-700">https://api.alphabrain.live</strong> (24ms)</span>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        </div>
      </footer>
    </div>
  );
};

export default App;
