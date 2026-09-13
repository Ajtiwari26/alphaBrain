import React, { useState, useEffect, useRef } from 'react';
import { EvaMeetingState } from '../types';
import { Mic, MicOff, Video, VideoOff, PhoneOff, Radio, Sparkles, Volume2 } from 'lucide-react';

interface Props {
  onLeave?: () => void;
}

const TRANSCRIPTS = [
  'Eva: Good afternoon Founder Ajay. LiveKit WebRTC bridge is established at 18ms latency.',
  'Eva: Mac Command Node v2.0 synchronized with cloud execution hub (api.alphabrain.live).',
  'Eva: All 14 departments and triage pipelines are healthy. Sprint fleet has active worker leases.',
  'Eva: Ready for voice instructions or executive directive on macOS.',
];

export const EvaMeetingScreen: React.FC<Props> = ({ onLeave }) => {
  const [meetingState, setMeetingState] = useState<EvaMeetingState>({
    room_name: 'alphabrain-executive-briefing',
    connected: true,
    participant_count: 2,
    audio_active: true,
    video_active: false,
    eva_speaking: true,
    rtt_ms: 18,
    packet_loss_percent: 0.0,
  });

  const [micMuted, setMicMuted] = useState(false);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [transcriptIndex, setTranscriptIndex] = useState(0);

  const timersRef = useRef<number[]>([]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setTranscriptIndex((prev) => (prev + 1) % TRANSCRIPTS.length);
    }, 4000);
    return () => {
      clearInterval(interval);
      timersRef.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  const handleInterrupt = () => {
    setMeetingState((prev) => ({ ...prev, eva_speaking: false }));
    const t = window.setTimeout(() => {
      setMeetingState((prev) => ({ ...prev, eva_speaking: true }));
    }, 2000);
    timersRef.current.push(t);
  };

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-6">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#E6391E] font-bold uppercase tracking-widest">
              MC-07 // TELEPHONY & WEBRTC
            </span>
            <span className="text-neutral-300">•</span>
            <span className="font-mono text-xs text-neutral-500 uppercase">
              LIVEKIT CLOUD SFU
            </span>
          </div>
          <h1 className="text-3xl font-bold font-sans tracking-tight mt-1 text-[#0A0A0A]">
            Eva Live Meeting
          </h1>
          <p className="font-mono text-xs text-neutral-500 mt-1">
            ROOM: <strong className="text-black">{meetingState.room_name}</strong> // RTT: <strong className="text-emerald-700">{meetingState.rtt_ms}ms</strong> // PACKET LOSS: <strong className="text-emerald-700">{meetingState.packet_loss_percent}%</strong>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 border border-[#0A0A0A] bg-neutral-50 font-mono text-xs">
            <Radio className="w-3.5 h-3.5 text-[#E6391E] animate-pulse" />
            <span className="font-bold">LIVE WEBRTC</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Avatar & Audio on Left, Transcript & Diagnostics on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Virtual Presence Frame */}
        <div className="lg:col-span-7 border border-[#0A0A0A] bg-white p-8 flex flex-col items-center justify-center relative min-h-[420px]">
          <div className="absolute top-4 left-4 font-mono text-[11px] text-[#E6391E] font-bold tracking-wider">
            [EVA CTO AI]
          </div>
          <div className="absolute top-4 right-4 font-mono text-[11px] text-neutral-400">
            48kHz OPUS STEREO
          </div>

          {/* Minimalist Vector Avatar Frame */}
          <div className="w-36 h-36 border-2 border-[#0A0A0A] bg-neutral-50 flex items-center justify-center relative shadow-sm">
            <svg
              className={`w-20 h-20 ${meetingState.eva_speaking ? 'text-[#E6391E]' : 'text-[#0A0A0A]'} transition-colors duration-200`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <circle cx="12" cy="12" r="9" />
              <path d="M8 12h8" />
              <path d="M12 8v8" />
              <circle cx="12" cy="12" r="3" fill="currentColor" fillOpacity="0.1" />
            </svg>
            {meetingState.eva_speaking && (
              <span className="absolute -bottom-3 font-mono text-[9px] bg-[#E6391E] text-white px-2 py-0.5 font-bold tracking-widest uppercase">
                SPEAKING
              </span>
            )}
          </div>

          {/* Audio Waveform Bars */}
          <div className="flex items-center justify-center gap-2 h-14 mt-10 mb-4 w-full max-w-md">
            {[35, 70, 95, 60, 85, 100, 75, 50, 90, 65, 40, 80, 55, 90, 70, 45].map((height, i) => (
              <div
                key={i}
                style={{
                  height: meetingState.eva_speaking ? `${Math.max(15, (height * ((i % 4) + 1)) % 100)}%` : '15%',
                }}
                className={`w-2 transition-all duration-150 ${
                  i % 2 === 0 ? 'bg-[#E6391E]' : 'bg-[#0A0A0A]'
                }`}
              />
            ))}
          </div>

          <div className="font-mono text-xs text-neutral-600 flex items-center gap-2">
            <Volume2 className="w-4 h-4 text-[#E6391E]" />
            <span>{meetingState.eva_speaking ? 'EVA AUDIO STREAM ACTIVE' : 'LISTENING TO FOUNDER'}</span>
          </div>
        </div>

        {/* Right Column: Real-time Transcript and Room Context */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="border border-[#0A0A0A] bg-white p-5 flex-1 flex flex-col">
            <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-3 mb-4">
              <span className="font-mono text-[11px] text-neutral-500 uppercase tracking-widest flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[#E6391E]" />
                REAL-TIME TRANSCRIPT // DATA CHANNEL
              </span>
              <span className="font-mono text-[10px] bg-neutral-100 px-2 py-0.5 text-neutral-600">
                ACTIVE
              </span>
            </div>
            <div className="bg-neutral-50 border border-neutral-200 p-4 font-mono text-sm leading-relaxed text-[#0A0A0A] flex-1 flex items-center">
              "{TRANSCRIPTS[transcriptIndex]}"
            </div>
          </div>

          {/* Room Specs Pill Box */}
          <div className="border border-[#0A0A0A] bg-white p-4 font-mono text-xs space-y-2">
            <div className="text-[10px] text-neutral-400 uppercase tracking-wider">SESSION PARAMETERS</div>
            <div className="flex justify-between text-neutral-600 border-b border-neutral-100 pb-1">
              <span>AUDIO CODEC:</span>
              <span className="font-bold text-black">Opus 48kHz (Fullband)</span>
            </div>
            <div className="flex justify-between text-neutral-600 border-b border-neutral-100 pb-1">
              <span>SECURITY:</span>
              <span className="font-bold text-black">DTLS-SRTP E2EE</span>
            </div>
            <div className="flex justify-between text-neutral-600">
              <span>PARTICIPANTS:</span>
              <span className="font-bold text-[#E6391E]">Ajay (Founder) + Eva (CTO)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Control Action Bar */}
      <div className="border border-[#0A0A0A] bg-neutral-50 p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setMicMuted(!micMuted)}
            className={`flex items-center gap-2 px-5 py-3 border border-[#0A0A0A] font-mono text-xs font-bold transition-all ${
              micMuted
                ? 'bg-neutral-200 text-neutral-600'
                : 'bg-white text-[#0A0A0A] hover:bg-neutral-100'
            }`}
          >
            {micMuted ? <MicOff className="w-4 h-4 text-neutral-500" /> : <Mic className="w-4 h-4 text-[#E6391E]" />}
            <span>{micMuted ? 'MIC: MUTED' : 'MIC: ACTIVE'}</span>
          </button>

          <button
            onClick={() => setCameraEnabled(!cameraEnabled)}
            className={`flex items-center gap-2 px-5 py-3 border border-[#0A0A0A] font-mono text-xs font-bold transition-all ${
              cameraEnabled
                ? 'bg-[#0A0A0A] text-white'
                : 'bg-white text-[#0A0A0A] hover:bg-neutral-100'
            }`}
          >
            {cameraEnabled ? <Video className="w-4 h-4 text-[#E6391E]" /> : <VideoOff className="w-4 h-4 text-neutral-500" />}
            <span>{cameraEnabled ? 'CAMERA: ON' : 'CAMERA: OFF'}</span>
          </button>

          <button
            onClick={handleInterrupt}
            className="flex items-center gap-2 px-5 py-3 border border-[#0A0A0A] bg-white font-mono text-xs font-bold text-[#E6391E] hover:bg-[#E6391E] hover:text-white transition-all tracking-wider"
          >
            <span>BARGE-IN / INTERRUPT</span>
          </button>
        </div>

        <button
          onClick={onLeave}
          className="flex items-center gap-2 px-6 py-3 border border-[#E6391E] bg-[#E6391E] text-white font-mono text-xs font-bold hover:bg-red-700 transition-all uppercase tracking-wider"
        >
          <PhoneOff className="w-4 h-4" />
          <span>END MEETING</span>
        </button>
      </div>
    </div>
  );
};
