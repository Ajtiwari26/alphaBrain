import React from 'react';
import { Users } from 'lucide-react';

interface Props {
  onSelectDept?: (dept: string) => void;
}

interface Department {
  num: string;
  name: string;
  count: string;
  active: boolean;
  lead: string;
  description: string;
}

export const DepartmentsScreen: React.FC<Props> = ({ onSelectDept }) => {
  const departments: Department[] = [
    { num: '01 //', name: 'Tech & Engineering', count: '4 AGENTS', active: true, lead: 'Gemini 3.1 Pro High', description: 'Autonomous coding, worktree workers, test suites & compiler gates' },
    { num: '02 //', name: 'Operations & SRE', count: '2 AGENTS', active: true, lead: 'Claude Opus 4.6', description: 'Lease management, watchdog monitors, circuit breakers & recovery' },
    { num: '03 //', name: 'Strategy & Architecture', count: '1 AGENT', active: true, lead: 'Claude Opus 4.6', description: 'System design directives, multi-agent protocol & canonical invariants' },
    { num: '04 //', name: 'Security & Enclave', count: '2 AGENTS', active: true, lead: 'Hardware Security Module', description: 'Keychain storage, Ed25519 signing, biometric access & audit trail' },
    { num: '05 //', name: 'Telephony & LiveKit', count: '1 AGENT', active: true, lead: 'Eva CTO Agent', description: 'WebRTC voice bridge, barge-in speech processing & LiveKit rooms' },
    { num: '06 //', name: 'QA & Gate Enforcement', count: '2 AGENTS', active: true, lead: 'Ruff & Pytest Subagents', description: 'Deterministic SafetyGate, zero-defect verification & CI healing' },
    { num: '07 //', name: 'DevOps & Deployments', count: '1 AGENT', active: false, lead: 'Vercel / Cloudflare Hub', description: 'Atomic PR promotion, fast-forward branch merges & live URLs' },
    { num: '08 //', name: 'Telemetry & Analytics', count: '2 AGENTS', active: true, lead: 'OC-EDS Engine', description: 'Google Cloud Code quota monitors, battery/thermal throttle tracking' },
    { num: '09 //', name: 'UI & Design Systems', count: '1 AGENT', active: true, lead: 'DeployMate Locomotive', description: 'Brutalist tokens, pixel-perfect layout & mobile/desktop parity' },
    { num: '10 //', name: 'Finance & Quota Vault', count: '1 AGENT', active: false, lead: 'API Ledger', description: 'AI token consumption, compute costs & provider quota balances' },
    { num: '11 //', name: 'Legal & Privacy Compliance', count: '1 AGENT', active: true, lead: 'GDPR / Privacy Gate', description: 'Transcript redactions, audit trail cryptographic hashing & purges' },
    { num: '12 //', name: 'Executive Office', count: '1 AGENT', active: true, lead: 'Founder Ajay', description: 'Founder approval sign-offs, emergency kill switch & directives' },
    { num: '13 //', name: 'Customer & Partner Ops', count: '1 AGENT', active: false, lead: 'Communications Relay', description: 'External integration hooks, customer portal & Webhook dispatch' },
    { num: '14 //', name: 'Autonomous Research', count: '2 AGENTS', active: true, lead: 'Gemini Research Agent', description: 'Web & GitHub grounding, architectural exploration & RFC drafts' },
  ];

  const activeCount = departments.filter((d) => d.active).length;

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-6 animate-screen-enter">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#E6391E] font-bold uppercase tracking-widest">
              ORGANIZATIONAL STRUCTURE
            </span>
            <span className="text-neutral-300">•</span>
            <span className="font-mono text-xs text-neutral-500 uppercase">
              14 AUTONOMOUS DEPARTMENTS
            </span>
          </div>
          <h1 className="text-3xl font-bold font-sans tracking-tight mt-1 text-[#0A0A0A]">
            Departments
          </h1>
          <p className="font-mono text-xs text-neutral-500 mt-1">
            Autonomous agent divisions, capability boundaries, and department leadership roster
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-4 py-2 border border-[#0A0A0A] bg-neutral-50 font-mono text-xs">
            STATUS: <strong className="text-emerald-700">{activeCount} / 14 ACTIVE</strong>
          </div>
        </div>
      </div>

      {/* 14 Departments Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {departments.map((dept) => (
          <div
            key={dept.name}
            onClick={() => onSelectDept?.(dept.name)}
            className="border border-[#0A0A0A] bg-white p-5 hover:bg-neutral-50 cursor-pointer transition-smooth hover-lift active:scale-[0.98] hover:border-[#E6391E] flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className={`font-mono text-xs font-bold ${dept.active ? 'text-[#E6391E]' : 'text-neutral-400'}`}>
                  {dept.num}
                </span>
                <span className={`font-mono text-[10px] font-bold px-2 py-0.5 border ${
                  dept.active
                    ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                    : 'border-neutral-200 bg-neutral-50 text-neutral-400'
                }`}>
                  {dept.active ? 'ACTIVE' : 'STANDBY'}
                </span>
              </div>

              <h2 className="text-lg font-bold font-sans text-[#0A0A0A] mt-2">
                {dept.name}
              </h2>
              <p className="text-xs text-neutral-600 mt-1 line-clamp-2">
                {dept.description}
              </p>
            </div>

            <div className="border-t border-neutral-200 mt-4 pt-3 flex items-center justify-between font-mono text-[11px]">
              <span className="text-neutral-500 flex items-center gap-1">
                <Users className="w-3.5 h-3.5 text-neutral-400" />
                {dept.count}
              </span>
              <span className="text-[#0A0A0A] font-medium truncate max-w-[150px]">
                {dept.lead}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Footer statistics summary */}
      <div className="border border-[#0A0A0A] bg-neutral-50 p-4 font-mono text-xs flex justify-between items-center">
        <span className="text-neutral-500">TOTAL CAPABILITY MATRIX</span>
        <span className="font-bold text-[#0A0A0A]">
          14 DEPARTMENTS CONFIGURED
        </span>
      </div>
    </div>
  );
};
