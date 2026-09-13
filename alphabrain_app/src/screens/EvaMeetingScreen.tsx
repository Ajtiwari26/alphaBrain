import React, { useState, useEffect, useRef } from 'react';
import { EvaMeetingState } from '../types';

interface Props {
  onLeave?: () => void;
}

const TRANSCRIPTS = [
  'Eva: Good afternoon Founder Ajay. LiveKit WebRTC bridge is established at 18ms latency.',
  'Eva: Telemetry shows Android device 10BF5P2AZF0010T synced over USB ADB reverse proxy.',
  'Eva: All 14 departments and triage pipelines are healthy. Sprint fleet has 4 active workers.',
  'Eva: Ready for voice instructions or executive directive.',
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
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
            MC-07 // TELEPHONY & WEBRTC
          </span>
          <span className="font-mono text-[10px] text-zinc-500 uppercase flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-pulse" />
            LIVEKIT ROOM
          </span>
        </div>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Eva Live Meeting
        </h2>
        <div className="font-mono text-[10px] text-zinc-500 mt-0.5">
          ROOM: {meetingState.room_name} // RTT: {meetingState.rtt_ms}ms // {meetingState.packet_loss_percent}% LOSS
        </div>
      </div>

      {/* Main Center Area: Avatar & Audio Visualizer */}
      <div className="flex-1 flex flex-col items-center justify-center py-4 space-y-4">
        {/* Eva Virtual Presence Frame */}
        <div className="w-full max-w-[280px] border-2 border-[#0A0A0A] bg-zinc-50 p-4 flex flex-col items-center relative">
          <div className="absolute top-2 left-2 font-mono text-[9px] text-[#E6391E] font-bold">
            [EVA AI]
          </div>
          <div className="absolute top-2 right-2 font-mono text-[9px] text-zinc-500">
            48kHz OPUS
          </div>

          {/* Minimalist Vector Avatar */}
          <div className="w-24 h-24 border border-[#0A0A0A] bg-white mt-4 flex items-center justify-center relative">
            <svg
              className={`w-14 h-14 ${meetingState.eva_speaking ? 'text-[#E6391E]' : 'text-[#0A0A0A]'} transition-colors`}
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
              <span className="absolute -bottom-2 font-mono text-[8px] bg-[#E6391E] text-white px-1.5 py-0.2 font-bold tracking-widest uppercase">
                SPEAKING
              </span>
            )}
          </div>

          {/* Audio Waveform Bars */}
          <div className="flex items-center justify-center gap-1.5 h-10 mt-6 mb-2">
            {[40, 75, 95, 60, 85, 100, 70, 50, 90, 65, 45, 80].map((height, i) => (
              <div
                key={i}
                style={{
                  height: meetingState.eva_speaking ? `${Math.max(15, (height * ((i % 3) + 1)) % 100)}%` : '15%',
                }}
                className={`w-1.5 transition-all duration-150 ${
                  i % 3 === 0 ? 'bg-[#E6391E]' : 'bg-[#0A0A0A]'
                }`}
              />
            ))}
          </div>

          <div className="font-mono text-[10px] text-zinc-500">
            {meetingState.eva_speaking ? 'EVA AUDIO STREAM ACTIVE' : 'LISTENING TO FOUNDER'}
          </div>
        </div>

        {/* Live Transcript Ticker */}
        <div className="w-full border border-[#0A0A0A] bg-white p-3">
          <div className="font-mono text-[9px] text-zinc-400 uppercase tracking-widest mb-1">
            REAL-TIME TRANSCRIPT // WEBRTC DATA CHANNEL
          </div>
          <p className="font-mono text-xs text-[#0A0A0A] min-h-[36px] leading-relaxed">
            {TRANSCRIPTS[transcriptIndex]}
          </p>
        </div>
      </div>

      {/* Meeting Action Bar */}
      <div className="space-y-2 pt-2">
        {/* Controls Grid */}
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => setMicMuted(!micMuted)}
            className={`h-12 border border-[#0A0A0A] font-mono text-xs font-bold transition-all flex items-center justify-center ${
              micMuted
                ? 'bg-zinc-100 text-zinc-500'
                : 'bg-white text-[#0A0A0A] hover:bg-zinc-100'
            }`}
          >
            {micMuted ? 'MIC: MUTED' : 'MIC: ON'}
          </button>

          <button
            onClick={() => setCameraEnabled(!cameraEnabled)}
            className={`h-12 border border-[#0A0A0A] font-mono text-xs font-bold transition-all flex items-center justify-center ${
              cameraEnabled
                ? 'bg-[#0A0A0A] text-white'
                : 'bg-white text-[#0A0A0A] hover:bg-zinc-100'
            }`}
          >
            {cameraEnabled ? 'CAM: ON' : 'CAM: OFF'}
          </button>

          <button
            onClick={handleInterrupt}
            className="h-12 border border-[#0A0A0A] font-mono text-xs font-bold text-[#E6391E] hover:bg-[#E6391E] hover:text-white transition-all flex items-center justify-center tracking-wider"
          >
            BARGE-IN
          </button>
        </div>

        {/* Leave Call Action */}
        <button
          onClick={onLeave}
          className="w-full border border-[#E6391E] bg-[#E6391E] text-white p-3.5 font-headline text-sm font-bold flex items-center justify-between hover:bg-red-700 active:scale-[0.99] transition-all"
        >
          <span>End Eva Meeting</span>
          <span className="font-mono text-xs uppercase tracking-widest">DISCONNECT ↗</span>
        </button>
      </div>
    </div>
  );
};
