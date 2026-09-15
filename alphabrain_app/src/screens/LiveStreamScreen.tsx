import React, { useState, useEffect, useMemo, useRef } from 'react';
import { mobileApi } from '../api/client';
import { AuditLogEntry } from '../types';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import {
  Terminal,
  Activity,
  Play,
  Pause,
  RefreshCw,
  Search,
  Filter,
  ShieldCheck,
  Cpu,
  User,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Trash2,
  Lock,
} from 'lucide-react';

export const LiveStreamScreen: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedActor, setSelectedActor] = useState<'ALL' | 'FOUNDER' | 'EVA' | 'SWARM' | 'SECURITY'>('ALL');
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const logContainerRef = useRef<HTMLDivElement>(null);

  const fetchLogs = async () => {
    try {
      const data = await mobileApi.getAuditTrail(50);
      setLogs(data);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error('Failed to fetch audit trail:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(() => {
      if (!paused) {
        fetchLogs();
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [paused]);

  const copyToClipboard = (text: string, fieldId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const getActorCategory = (actor: string): 'FOUNDER' | 'EVA' | 'SWARM' | 'SECURITY' => {
    const a = actor.toLowerCase();
    if (a.includes('founder')) return 'FOUNDER';
    if (a.includes('eva')) return 'EVA';
    if (a.includes('safety') || a.includes('gate') || a.includes('tombstone') || a.includes('security'))
      return 'SECURITY';
    return 'SWARM';
  };

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const q = searchQuery.toLowerCase();
      const matchesQuery =
        !q ||
        log.actor.toLowerCase().includes(q) ||
        log.action_type.toLowerCase().includes(q) ||
        log.resource_id.toLowerCase().includes(q) ||
        log.sha256_hash.toLowerCase().includes(q);

      if (!matchesQuery) return false;

      if (selectedActor === 'ALL') return true;
      return getActorCategory(log.actor) === selectedActor;
    });
  }, [logs, searchQuery, selectedActor]);

  const formatRelativeTime = (ts: number): string => {
    const diffSeconds = Math.max(0, Math.floor(Date.now() / 1000 - ts));
    if (diffSeconds < 5) return 'Just now';
    if (diffSeconds < 60) return `${diffSeconds}s ago`;
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh] animate-screen-enter pb-16">
      {/* Top Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase flex items-center gap-1.5">
            <Terminal className="w-3 h-3 text-[#E6391E]" />
            MISSION CONTROL • EXECUTION STREAM
          </span>
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 font-mono text-[10px] font-bold px-2 py-0.5 border ${
                paused
                  ? 'border-zinc-300 text-zinc-400 bg-zinc-100'
                  : 'border-[#E6391E] text-[#E6391E] bg-red-50'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  paused ? 'bg-zinc-400' : 'bg-[#E6391E] animate-ping'
                }`}
              />
              {paused ? 'PAUSED' : 'LIVE 3s'}
            </span>
          </div>
        </div>

        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Execution Log
        </h2>
        <p className="font-sans text-xs text-zinc-500 mt-0.5">
          Cryptographically signed immutable audit trail of all autonomous swarm actions, founder overrides, and Eva syntheses.
        </p>
      </div>

      {/* Metrics & Stream Cadence Bar */}
      <div className="grid grid-cols-3 gap-2 my-3">
        <div className="border border-[#0A0A0A] p-2.5 bg-zinc-50 flex flex-col">
          <span className="font-mono text-[9px] text-zinc-500 uppercase">EVENTS STREAMED</span>
          <span className="font-mono text-lg font-black text-[#0A0A0A] mt-0.5">
            {loading ? '...' : logs.length}
          </span>
          <span className="font-mono text-[9px] text-zinc-400">in-memory buffer</span>
        </div>

        <div className="border border-[#0A0A0A] p-2.5 bg-zinc-50 flex flex-col">
          <span className="font-mono text-[9px] text-zinc-500 uppercase">STREAM STATUS</span>
          <span
            className={`font-mono text-lg font-black mt-0.5 ${
              paused ? 'text-zinc-500' : 'text-emerald-600'
            }`}
          >
            {paused ? 'HALTED' : 'ACTIVE'}
          </span>
          <span className="font-mono text-[9px] text-zinc-400">polling every 3s</span>
        </div>

        <div className="border border-[#0A0A0A] p-2.5 bg-zinc-50 flex flex-col">
          <span className="font-mono text-[9px] text-zinc-500 uppercase">INTEGRITY HASH</span>
          <span className="font-mono text-xs font-bold text-[#E6391E] mt-1.5 truncate">
            {logs[0] ? logs[0].sha256_hash.slice(0, 8) + '...' : 'SHA-256'}
          </span>
          <span className="font-mono text-[9px] text-zinc-400">latest block</span>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="space-y-2 mb-3">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder="Search action, actor, resource ID or hash..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs font-mono bg-zinc-50 border border-[#0A0A0A] placeholder:text-zinc-400 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[#0A0A0A]"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-black"
            >
              ×
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px] font-mono scrollbar-none">
          {(['ALL', 'FOUNDER', 'EVA', 'SWARM', 'SECURITY'] as const).map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedActor(cat)}
              className={`px-2.5 py-1 border whitespace-nowrap font-bold transition-colors ${
                selectedActor === cat
                  ? cat === 'FOUNDER'
                    ? 'bg-[#E6391E] text-white border-[#E6391E]'
                    : cat === 'EVA'
                    ? 'bg-[#0A0A0A] text-white border-[#0A0A0A]'
                    : cat === 'SECURITY'
                    ? 'bg-amber-600 text-white border-amber-600'
                    : 'bg-zinc-800 text-white border-zinc-800'
                  : 'bg-white text-zinc-600 border-zinc-300 hover:border-black'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Audit Log Stream Container */}
      <div
        ref={logContainerRef}
        className="flex-1 p-2 font-mono text-xs overflow-y-auto max-h-[50vh] bg-zinc-50 border border-[#0A0A0A] divide-y divide-zinc-200"
      >
        {loading ? (
          <div className="p-8 flex flex-col items-center justify-center space-y-3">
            <LoadingSpinner size="md" label="Connecting to cryptographic audit stream..." />
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="p-8 text-center text-zinc-400 space-y-1">
            <Terminal className="w-8 h-8 text-zinc-300 mx-auto mb-2" />
            <p className="font-bold text-zinc-600">No events matched your filter</p>
            <p className="text-[10px]">Change the filter chip or clear your search term.</p>
          </div>
        ) : (
          filteredLogs.map((log) => {
            const isExpanded = expandedEventId === log.event_id;
            const category = getActorCategory(log.actor);
            const timeFormatted = formatRelativeTime(log.timestamp);
            const fullTimeStr = new Date(log.timestamp * 1000).toLocaleTimeString();

            return (
              <div
                key={log.event_id}
                onClick={() => setExpandedEventId(isExpanded ? null : log.event_id)}
                className={`p-2.5 bg-white hover:bg-zinc-100/80 transition-smooth cursor-pointer ${
                  isExpanded ? 'ring-1 ring-[#0A0A0A] bg-zinc-50' : ''
                }`}
              >
                {/* Event Top Line */}
                <div className="flex items-center justify-between gap-2 text-[10px]">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`font-mono text-[9px] font-black px-1.5 py-0.5 border ${
                        category === 'FOUNDER'
                          ? 'border-[#E6391E] bg-red-50 text-[#E6391E]'
                          : category === 'EVA'
                          ? 'border-[#0A0A0A] bg-[#0A0A0A] text-white'
                          : category === 'SECURITY'
                          ? 'border-amber-600 bg-amber-50 text-amber-700'
                          : 'border-zinc-400 bg-zinc-100 text-zinc-700'
                      }`}
                    >
                      {log.actor.toUpperCase()}
                    </span>
                    <span className="font-bold text-[#0A0A0A] text-[11px] truncate">
                      {log.action_type}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-zinc-400 text-[10px]">{timeFormatted}</span>
                    <span className="font-mono text-[9px] text-zinc-400 bg-zinc-100 px-1 py-0.5 border border-zinc-200">
                      {log.sha256_hash.slice(0, 6)}
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="w-3.5 h-3.5 text-zinc-500" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
                    )}
                  </div>
                </div>

                {/* Event Target Resource */}
                <div className="mt-1 flex items-center justify-between text-[11px]">
                  <span className="text-zinc-600 truncate">
                    → <span className="text-zinc-900 font-semibold">{log.resource_id}</span>
                  </span>
                </div>

                {/* Expanded Payload & Cryptographic Inspector */}
                {isExpanded && (
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className="mt-3 pt-3 border-t border-zinc-200 space-y-2 text-[10px] font-mono animate-screen-enter"
                  >
                    <div className="flex items-center justify-between text-zinc-500">
                      <span>EVENT ID: {log.event_id}</span>
                      <span>RECORDED: {fullTimeStr}</span>
                    </div>

                    <div>
                      <div className="flex items-center justify-between text-zinc-500 mb-1">
                        <span>SHA-256 PROOF HASH</span>
                        <button
                          onClick={(e) => copyToClipboard(log.sha256_hash, log.event_id, e)}
                          className="flex items-center gap-1 text-[#E6391E] hover:underline"
                        >
                          {copiedField === log.event_id ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-600" />
                              <span className="text-emerald-600">COPIED</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span>COPY HASH</span>
                            </>
                          )}
                        </button>
                      </div>
                      <div className="p-1.5 bg-zinc-100 border border-zinc-200 break-all select-all text-[9px] text-zinc-700">
                        {log.sha256_hash}
                      </div>
                    </div>

                    {log.details && Object.keys(log.details).length > 0 && (
                      <div>
                        <span className="text-zinc-500 block mb-1">STRUCTURED AUDIT PAYLOAD</span>
                        <pre className="p-2 bg-zinc-900 text-zinc-100 text-[10px] overflow-x-auto border border-black max-h-36">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Stream Controls */}
      <div className="border-t border-[#0A0A0A] pt-3 flex gap-2">
        <button
          onClick={() => setPaused(!paused)}
          className={`flex-1 py-3 border font-mono text-xs font-bold flex items-center justify-center gap-1.5 transition-colors ${
            paused
              ? 'bg-emerald-600 text-white border-emerald-700 hover:bg-emerald-700'
              : 'border-[#0A0A0A] bg-white text-[#0A0A0A] hover:bg-black hover:text-white'
          }`}
        >
          {paused ? (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>RESUME STREAM</span>
            </>
          ) : (
            <>
              <Pause className="w-3.5 h-3.5 fill-current" />
              <span>PAUSE STREAM</span>
            </>
          )}
        </button>

        <button
          onClick={fetchLogs}
          className="flex-1 bg-[#0A0A0A] text-white py-3 font-mono text-xs font-bold hover:bg-[#E6391E] transition-colors flex items-center justify-center gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>FORCE REFRESH</span>
        </button>
      </div>
    </div>
  );
};
