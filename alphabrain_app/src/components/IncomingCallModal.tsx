import React, { useEffect, useRef } from 'react';

interface CallData {
  call_id: string;
  caller_name: string;
  caller_role: string;
  title: string;
  prompt_summary: string;
  task_id?: string;
}

interface Props {
  call: CallData;
  onAccept: () => void;
  onDecline: () => void;
}

export const IncomingCallModal: React.FC<Props> = ({ call, onAccept, onDecline }) => {
  const audioCtxRef = useRef<AudioContext | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const AudioContextClass = (window.AudioContext || (window as any).webkitAudioContext) as typeof AudioContext;
    if (AudioContextClass) {
      const ctx = new AudioContextClass();
      audioCtxRef.current = ctx;

      const playChime = () => {
        if (ctx.state === 'suspended') {
          ctx.resume().catch(() => {});
        }
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, ctx.currentTime);
        osc.frequency.setValueAtTime(480, ctx.currentTime + 0.2);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.5);
      };

      playChime();
      intervalRef.current = setInterval(playChime, 2500);
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (audioCtxRef.current) audioCtxRef.current.close().catch(() => {});
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-white/95 backdrop-blur-md text-[#0A0A0A] p-6">
      <div className="text-xs font-mono font-bold text-zinc-500 mb-2 tracking-widest uppercase">
        ALPHABRAIN IN-APP VOIP CALL • URGENT INTEL
      </div>
      <div className="relative mb-6 mt-2">
        <div className="w-28 h-28 rounded-full bg-emerald-500 animate-ping absolute opacity-20 inset-0 m-auto"></div>
        <div className="w-28 h-28 rounded-full bg-zinc-50 border-4 border-[#0A0A0A] relative flex items-center justify-center text-4xl font-bold shadow-[4px_4px_0px_#0A0A0A] text-[#0A0A0A] overflow-hidden">
          {call.caller_name ? call.caller_name.charAt(0) : 'E'}
        </div>
      </div>
      <h1 className="text-2xl font-bold font-sans text-[#0A0A0A] mb-1">{call.caller_name || 'Eva (DeployMate CTO)'}</h1>
      <h2 className="text-xs font-mono font-semibold text-[#FF3B00] uppercase tracking-wider mb-6">{call.caller_role || 'Autonomous AI Architect'}</h2>
      
      <div className="bg-zinc-50 p-5 rounded-none w-full max-w-sm mb-10 border-2 border-[#0A0A0A] shadow-[4px_4px_0px_#0A0A0A]">
        <div className="flex items-center gap-1.5 mb-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <h3 className="font-mono font-bold text-xs uppercase tracking-wider text-[#0A0A0A] truncate">{call.title}</h3>
        </div>
        <p className="text-[#0A0A0A] text-xs font-sans leading-relaxed">{call.prompt_summary}</p>
      </div>
      
      <div className="flex w-full max-w-sm justify-around mt-auto mb-8">
        <button 
          onClick={onDecline} 
          className="flex flex-col items-center group cursor-pointer"
        >
          <div className="w-16 h-16 rounded-full bg-red-500 border-2 border-[#0A0A0A] flex items-center justify-center mb-2 shadow-[3px_3px_0px_#0A0A0A] group-hover:translate-x-0.5 group-hover:translate-y-0.5 transition-all">
            <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" /></svg>
          </div>
          <span className="text-xs font-mono font-bold uppercase text-[#0A0A0A]">Decline</span>
        </button>
        <button 
          onClick={onAccept} 
          className="flex flex-col items-center group cursor-pointer"
        >
          <div className="w-16 h-16 rounded-full bg-emerald-500 border-2 border-[#0A0A0A] flex items-center justify-center mb-2 shadow-[3px_3px_0px_#0A0A0A] group-hover:translate-x-0.5 group-hover:translate-y-0.5 transition-all animate-bounce">
            <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
          </div>
          <span className="text-xs font-mono font-bold uppercase text-[#0A0A0A]">Accept Call</span>
        </button>
      </div>
    </div>
  );
};
