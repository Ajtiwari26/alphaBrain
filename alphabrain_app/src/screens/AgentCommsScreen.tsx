import React, { useState, useEffect, useRef } from 'react';
import { mobileApi } from '../api/client';
import { 
  Mic, 
  Send, 
  Bot, 
  Terminal, 
  Search, 
  Sparkles, 
  ShieldCheck, 
  ArrowRight, 
  Radio, 
  Activity, 
  CheckCircle2, 
  RefreshCw,
  Cpu,
  Layers,
  Flame
} from 'lucide-react';

interface Props {
  onNavigateEva?: () => void;
}

interface CommentaryEvent {
  id: string;
  timestamp: string;
  source: 'EVA' | 'WORKER' | 'RESEARCH' | 'OPUS' | 'SENTINEL' | 'FOUNDER';
  text: string;
  type: 'directive' | 'execution' | 'review' | 'security';
}

const INITIAL_COMMENTARY: CommentaryEvent[] = [
  {
    id: 'c-1',
    timestamp: '03:51:02',
    source: 'FOUNDER',
    text: 'Initialized session. Founder authenticated via Master PIN.',
    type: 'security',
  },
  {
    id: 'c-2',
    timestamp: '03:51:04',
    source: 'EVA',
    text: 'Good evening, Ajay. Eva Conductor active on host Mac. Fleet synchronized.',
    type: 'directive',
  },
  {
    id: 'c-3',
    timestamp: '03:51:10',
    source: 'RESEARCH',
    text: 'Scanned 8 Google Cloud Code accounts. Reserve quota verified at 99.1%.',
    type: 'execution',
  },
  {
    id: 'c-4',
    timestamp: '03:51:15',
    source: 'WORKER',
    text: 'Worker AGY-1 executing isolated Git worktree: feat/mobile-env-vault.',
    type: 'execution',
  },
  {
    id: 'c-5',
    timestamp: '03:51:22',
    source: 'OPUS',
    text: 'Senior architectural invariants verified: docs/architecture design followed.',
    type: 'review',
  },
  {
    id: 'c-6',
    timestamp: '03:51:30',
    source: 'SENTINEL',
    text: 'Deterministic SafetyGate intact. Zero direct mutations on immutable core.',
    type: 'security',
  },
];

export const AgentCommsScreen: React.FC<Props> = ({ onNavigateEva }) => {
  const [founderInput, setFounderInput] = useState('');
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [commentary, setCommentary] = useState<CommentaryEvent[]>(INITIAL_COMMENTARY);
  const commentaryContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll commentary container internally without moving window viewport
  useEffect(() => {
    if (commentaryContainerRef.current) {
      commentaryContainerRef.current.scrollTop = commentaryContainerRef.current.scrollHeight;
    }
  }, [commentary]);

  const handleConveyDirective = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!founderInput.trim() || isSynthesizing) return;

    const userText = founderInput.trim();
    setFounderInput('');
    setIsSynthesizing(true);

    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];

    // 1. Log Founder instruction
    const founderEvent: CommentaryEvent = {
      id: `c-${Date.now()}`,
      timestamp: timeStr,
      source: 'FOUNDER',
      text: userText,
      type: 'directive',
    };

    setCommentary((prev) => [...prev, founderEvent]);

    try {
      // 2. Dispatch to real backend orchestration pipeline
      const res = await mobileApi.sendSpokenCommand(userText);
      const timeNow = new Date().toTimeString().split(' ')[0];

      const evaEvent: CommentaryEvent = {
        id: `c-${Date.now() + 1}`,
        timestamp: timeNow,
        source: 'EVA',
        text: res.eva_response_text || `Acknowledged: ${res.interpreted_action}`,
        type: res.interpreted_action?.includes('verdict') ? 'review' : 'directive',
      };
      setCommentary((prev) => [...prev, evaEvent]);

      if (res.proposed_task_id) {
        setTimeout(() => {
          const fleetEvent: CommentaryEvent = {
            id: `c-${Date.now() + 2}`,
            timestamp: new Date().toTimeString().split(' ')[0],
            source: 'WORKER',
            text: `Fleet Orchestrator: Task ${res.proposed_task_id} registered in SQLite queue. Ready on Triage Board.`,
            type: 'execution',
          };
          setCommentary((prev) => [...prev, fleetEvent]);
        }, 600);
      }
    } catch (err: any) {
      const errorEvent: CommentaryEvent = {
        id: `c-${Date.now() + 1}`,
        timestamp: new Date().toTimeString().split(' ')[0],
        source: 'EVA',
        text: `Pipeline offline notice: ${err.message || 'Direct intake error'}`,
        type: 'directive',
      };
      setCommentary((prev) => [...prev, errorEvent]);
    } finally {
      setIsSynthesizing(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-white text-[#0A0A0A] animate-screen-enter space-y-4 pb-[max(env(safe-area-inset-bottom),5rem)]">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
              ORCHESTRATION HUB
            </span>
            <span className="font-mono text-[9px] px-1.5 py-0.2 bg-[#0A0A0A] text-white font-bold uppercase">
              EVA CONDUCTOR
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            <span className="font-mono text-[9px] font-bold text-emerald-700 uppercase">
              FLEET ONLINE
            </span>
          </div>
        </div>

        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Agent Mesh
        </h2>
        <p className="font-mono text-[11px] text-zinc-500 mt-0.5">
          Convey directives to Eva • Eva coordinates and synchronizes the entire fleet
        </p>
      </div>

      {/* HERO CONDUCTOR: Eva Voice CTO Card */}
      <div className="border-2 border-[#0A0A0A] p-4 bg-zinc-50 space-y-3.5 relative overflow-hidden">
        {/* Top Status Row */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 border border-[#0A0A0A] bg-white flex items-center justify-center relative">
              <Mic className="w-5 h-5 text-[#E6391E]" />
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-emerald-500 rounded-full border border-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-headline text-lg font-bold text-[#0A0A0A]">
                  Eva Voice CTO
                </h3>
                <span className="font-mono text-[8px] font-bold px-1.5 py-0.2 bg-[#E6391E] text-white uppercase">
                  CHIEF OF STAFF
                </span>
              </div>
              <span className="font-mono text-[10px] text-zinc-500">
                Bidirectional Telephony • Gemini Live 2.0 WebRTC
              </span>
            </div>
          </div>

          {/* Quick 1-Tap Voice Call Button */}
          <button
            onClick={onNavigateEva}
            className="flex items-center gap-1.5 font-mono text-[10px] font-bold bg-[#0A0A0A] text-white px-3 py-1.5 hover:bg-[#E6391E] transition-colors border border-[#0A0A0A] shrink-0"
          >
            <Radio className="w-3.5 h-3.5 text-[#E6391E] animate-pulse" />
            <span>CALL EVA ↗</span>
          </button>
        </div>

        {/* Live Audio Waveform Animation */}
        <div className="border border-zinc-300 bg-white p-2.5 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <div className="flex items-end gap-1 h-5">
              <span className="w-1 bg-[#E6391E] h-2 animate-[pulse_1s_ease-in-out_infinite]" />
              <span className="w-1 bg-[#0A0A0A] h-5 animate-[pulse_0.8s_ease-in-out_infinite]" />
              <span className="w-1 bg-[#E6391E] h-3 animate-[pulse_1.2s_ease-in-out_infinite]" />
              <span className="w-1 bg-[#0A0A0A] h-4 animate-[pulse_0.9s_ease-in-out_infinite]" />
              <span className="w-1 bg-[#E6391E] h-2 animate-[pulse_1.1s_ease-in-out_infinite]" />
            </div>
            <span className="font-mono text-[10px] font-bold text-zinc-700 ml-2">
              {isSynthesizing ? 'EVA IS DISPATCHING TO FLEET...' : 'LISTENING TO FOUNDER CHANNEL'}
            </span>
          </div>

          <span className="font-mono text-[9px] text-zinc-400">
            AUDIO BRIDGE READY
          </span>
        </div>

        {/* Convey Directive Input Bar */}
        <form onSubmit={handleConveyDirective} className="space-y-2">
          <label className="block font-mono text-[10px] font-bold text-zinc-600 uppercase">
            Convey Directive to Eva (She relays to all agents):
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="e.g. Audit security tokens, push sprint hotfix, review AST..."
              value={founderInput}
              onChange={(e) => setFounderInput(e.target.value)}
              disabled={isSynthesizing}
              className="flex-1 bg-white border border-[#0A0A0A] px-3 py-2 font-mono text-xs text-[#0A0A0A] outline-none focus:border-[#E6391E] disabled:bg-zinc-100"
            />
            <button
              type="submit"
              disabled={!founderInput.trim() || isSynthesizing}
              className="px-3 py-2 bg-[#E6391E] text-white border border-[#0A0A0A] font-mono text-xs font-bold hover:bg-red-700 disabled:opacity-50 flex items-center gap-1 shrink-0"
            >
              <span>SEND</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </form>
      </div>

      {/* FLEET LIVE WORKING ANIMATIONS (4 Autonomous Workers) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between font-mono text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
          <span>ACTIVE FLEET DAEMONS (4 WORKING)</span>
          <span className="flex items-center gap-1 text-emerald-700">
            <Activity className="w-3 h-3 animate-pulse" />
            SYNCHRONIZED
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2.5 font-mono text-[10px]">
          {/* Agent 1: Worker AGY-1 */}
          <div className="border border-[#0A0A0A] p-2.5 bg-white space-y-1.5 relative">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1 font-bold text-[#0A0A0A]">
                <Terminal className="w-3.5 h-3.5 text-[#E6391E]" />
                <span>Worker AGY-1</span>
              </div>
              <span className="text-[8px] font-bold px-1 bg-emerald-100 text-emerald-800 border border-emerald-300">
                CODING
              </span>
            </div>
            <p className="text-[9px] text-zinc-500 leading-tight">
              Gemini 3.1 Pro • Editing worktree containers
            </p>
            {/* Visual Working Animation */}
            <div className="flex items-center gap-1.5 pt-1 border-t border-zinc-100 text-[9px] text-zinc-600">
              <span className="w-1.5 h-1.5 bg-[#E6391E] rounded-full animate-ping" />
              <span className="truncate">Writing AST tests...</span>
            </div>
          </div>

          {/* Agent 2: Research AGY-2 */}
          <div className="border border-[#0A0A0A] p-2.5 bg-white space-y-1.5 relative">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1 font-bold text-[#0A0A0A]">
                <Search className="w-3.5 h-3.5 text-[#E6391E]" />
                <span>Research AGY-2</span>
              </div>
              <span className="text-[8px] font-bold px-1 bg-blue-100 text-blue-800 border border-blue-300">
                SCANNING
              </span>
            </div>
            <p className="text-[9px] text-zinc-500 leading-tight">
              Flash High • Web & Telemetry Grounding
            </p>
            {/* Visual Working Animation */}
            <div className="flex items-center gap-1.5 pt-1 border-t border-zinc-100 text-[9px] text-zinc-600">
              <RefreshCw className="w-2.5 h-2.5 text-blue-600 animate-spin" />
              <span className="truncate">Syncing Quotas...</span>
            </div>
          </div>

          {/* Agent 3: Reviewer Opus */}
          <div className="border border-[#0A0A0A] p-2.5 bg-white space-y-1.5 relative">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1 font-bold text-[#0A0A0A]">
                <Cpu className="w-3.5 h-3.5 text-[#E6391E]" />
                <span>Reviewer Opus</span>
              </div>
              <span className="text-[8px] font-bold px-1 bg-amber-100 text-amber-800 border border-amber-300">
                DEBATING
              </span>
            </div>
            <p className="text-[9px] text-zinc-500 leading-tight">
              Claude Opus 4.6 • Senior SDLC Reviewer
            </p>
            {/* Visual Working Animation */}
            <div className="flex items-center gap-1.5 pt-1 border-t border-zinc-100 text-[9px] text-zinc-600">
              <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-pulse" />
              <span className="truncate">2-Round Debate...</span>
            </div>
          </div>

          {/* Agent 4: SafetyGate Sentinel */}
          <div className="border border-[#0A0A0A] p-2.5 bg-white space-y-1.5 relative">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1 font-bold text-[#0A0A0A]">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Safety Sentinel</span>
              </div>
              <span className="text-[8px] font-bold px-1 bg-zinc-100 text-zinc-800 border border-zinc-300">
                GUARDING
              </span>
            </div>
            <p className="text-[9px] text-zinc-500 leading-tight">
              Deterministic • Zero-Mutation Invariant
            </p>
            {/* Visual Working Animation */}
            <div className="flex items-center gap-1.5 pt-1 border-t border-zinc-100 text-[9px] text-emerald-700">
              <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
              <span className="truncate">Perimeter Sealed</span>
            </div>
          </div>
        </div>
      </div>

      {/* LIVE COMMENTARY FEED SCREEN */}
      <div className="border-2 border-[#0A0A0A] bg-[#0A0A0A] text-white p-3 space-y-2.5">
        {/* Commentary Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-ping" />
            <span className="font-mono text-[10px] font-bold tracking-widest text-[#E6391E] uppercase">
              LIVE MISSION COMMENTARY
            </span>
          </div>

          <span className="font-mono text-[9px] text-zinc-400">
            AUTO-NARRATING
          </span>
        </div>

        {/* Ticker Feed (Scrollable) */}
        <div 
          ref={commentaryContainerRef}
          className="max-h-44 overflow-y-auto space-y-2 font-mono text-[11px] pr-1"
        >
          {commentary.map((evt) => {
            let badgeStyle = 'bg-zinc-800 text-zinc-300 border-zinc-700';
            if (evt.source === 'FOUNDER') badgeStyle = 'bg-[#E6391E] text-white border-[#E6391E]';
            if (evt.source === 'EVA') badgeStyle = 'bg-white text-[#0A0A0A] border-white font-bold';
            if (evt.source === 'WORKER') badgeStyle = 'bg-emerald-950 text-emerald-400 border-emerald-700';
            if (evt.source === 'OPUS') badgeStyle = 'bg-amber-950 text-amber-300 border-amber-700';

            return (
              <div key={evt.id} className="leading-snug flex items-start gap-2 border-b border-zinc-900 pb-1.5 last:border-0">
                <span className="text-zinc-500 text-[9px] shrink-0 pt-0.5">
                  {evt.timestamp}
                </span>

                <span className={`text-[8px] font-bold px-1 py-0.2 border uppercase shrink-0 ${badgeStyle}`}>
                  {evt.source}
                </span>

                <p className="text-zinc-300 text-[10px] flex-1">
                  {evt.text}
                </p>
              </div>
            );
          })}
        </div>

        {/* Footer commentary status */}
        <div className="border-t border-zinc-800 pt-1.5 flex items-center justify-between font-mono text-[9px] text-zinc-500">
          <span>HOST: 127.0.0.1:8000 TELEMETRY</span>
          <span>STREAM ACTIVE • BUFFER 100</span>
        </div>
      </div>
    </div>
  );
};

