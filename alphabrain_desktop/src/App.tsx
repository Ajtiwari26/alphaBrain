import React, { useState } from 'react';
import { ScreenId } from './types';
import { M01_NodeSetup } from './screens/M01_NodeSetup';
import { M02_PairingStation } from './screens/M02_PairingStation';
import { M03_CommandNode } from './screens/M03_CommandNode';
import { M04_SecurityEnclave } from './screens/M04_SecurityEnclave';
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
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          {/* Brand Mark */}
          <div className="flex items-center gap-3 shrink-0 mr-4">
            <div className="w-7 h-7 bg-[#0A0A0A] flex items-center justify-center text-white font-mono font-bold text-sm">
              α
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-mono font-bold tracking-tight text-sm uppercase">
                AlphaBrain
              </span>
              <span className="hidden md:inline text-[11px] font-mono text-neutral-500 uppercase tracking-widest">
                Command Node v2.0 (macOS)
              </span>
            </div>
          </div>

          {/* Symmetrical Parity Navigation Tabs */}
          <nav className="flex h-14 font-mono text-xs overflow-x-auto no-scrollbar">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentScreen === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentScreen(item.id)}
                  className={`flex items-center gap-1.5 px-3 h-full border-l border-[#0A0A0A] transition-colors relative whitespace-nowrap ${
                    isActive
                      ? 'bg-neutral-100 font-bold text-black border-b-2 border-b-[#E6391E]'
                      : 'hover:bg-neutral-50 text-neutral-600'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-[#E6391E]' : 'text-neutral-400'}`} />
                  <span className="text-[9px] text-neutral-400 uppercase">{item.code}</span>
                  <span className="uppercase tracking-wider text-[11px]">{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Quick Telemetry & Status Pill */}
          <div className="hidden lg:flex items-center gap-3 border-l border-[#0A0A0A] pl-4 h-14 shrink-0">
            <div className="flex items-center gap-1.5 font-mono text-xs">
              <Radio className="w-3.5 h-3.5 text-emerald-600 animate-pulse" />
              <span className="font-bold">CLOUD SYNCED</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Screen Content View */}
      <main className="flex-1 overflow-y-auto">
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

      {/* Bottom Status Bar */}
      <footer className="border-t border-[#0A0A0A] bg-neutral-50 py-2 px-6 font-mono text-[11px] text-neutral-600 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <span>HOST: <strong className="text-black">Apple M4 Max (macOS 15)</strong></span>
          <span>BRANCH: <strong className="text-[#E6391E]">alpha/tsk_eva_c1b1b4ca54ca</strong></span>
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
