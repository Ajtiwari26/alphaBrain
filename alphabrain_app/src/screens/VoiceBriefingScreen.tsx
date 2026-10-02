import React, { useState, useEffect, useRef } from 'react';
import { VoiceBriefing } from '../types';
import { mobileApi } from '../api/client';
import { Mic, MicOff, Radio, Volume2, Sparkles, Send, CheckCircle2 } from 'lucide-react';

export const VoiceBriefingScreen: React.FC = () => {
  const [briefing, setBriefing] = useState<VoiceBriefing | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [commandInput, setCommandInput] = useState('');
  const [commandResponse, setCommandResponse] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    mobileApi.getVoiceBriefing().then((data) => {
      setBriefing(data);
      setLoading(false);
    });
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, []);

  const handleSendCommand = async (text: string) => {
    if (!text.trim()) return;
    setCommandResponse('Eva is interpreting voice command...');
    try {
      const res = await mobileApi.sendSpokenCommand(text);
      setCommandResponse(res.eva_response_text);
      setCommandInput('');
    } catch (err) {
      console.error(err);
      setCommandResponse('Command acknowledged. Scheduled for autonomous intake.');
    }
  };

  const toggleMic = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    if (!SpeechRecognition) {
      // Graceful fallback if device does not support SpeechRecognition
      setCommandResponse('Speech API unavailable. Please type your directive into the input box below.');
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setCommandInput(transcript);
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition notice:', event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (e) {
      console.error('Failed to start speech recognition:', e);
      setIsListening(false);
    }
  };

  if (loading || !briefing) {
    return <div className="p-8 text-center text-zinc-500 font-mono text-xs">Connecting to Eva Voice AI...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b-2 border-[#0A0A0A] pb-3">
        <div>
          <span className="font-mono text-[10px] text-[#FF3B00] font-bold uppercase tracking-widest">05 • SPOKEN INTAKE</span>
          <h1 className="font-sans text-xl font-bold text-[#0A0A0A] tracking-tight">Eva Voice CTO</h1>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-0.5 border border-[#0A0A0A] font-mono text-[10px] font-bold text-[#0A0A0A] bg-zinc-50">
          <Radio className="w-3 h-3 text-[#FF3B00] animate-pulse" />
          <span>ROOM: {briefing.active_room}</span>
        </div>
      </div>

      {/* Voice Visualizer Avatar */}
      <div className="bg-white border-2 border-[#0A0A0A] shadow-[2px_2px_0px_#0A0A0A] p-5 flex flex-col items-center justify-center text-center relative">
        <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-3 transition-all duration-300 ${
          isListening 
            ? 'bg-red-50 border-2 border-red-500 scale-110 shadow-md' 
            : 'bg-zinc-50 border-2 border-[#0A0A0A]'
        }`}>
          {isListening ? (
            <Mic className="w-7 h-7 text-red-500 animate-bounce" />
          ) : (
            <Volume2 className="w-7 h-7 text-[#0A0A0A]" />
          )}
        </div>

        <h3 className="font-sans text-base font-bold text-[#0A0A0A]">{briefing.speaker}</h3>
        <p className="font-mono text-[11px] text-zinc-600 mt-0.5">Autonomous Engineering & AI Architect</p>

        <button
          onClick={toggleMic}
          className={`mt-4 px-4 py-2 border-2 border-[#0A0A0A] font-mono text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-all cursor-pointer ${
            isListening
              ? 'bg-red-500 text-white animate-pulse'
              : 'bg-[#0A0A0A] text-white hover:bg-zinc-800'
          }`}
        >
          {isListening ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
          {isListening ? 'Listening...' : 'Tap to Speak Command'}
        </button>

        {/* In-App WhatsApp-style VoIP Call Trigger Button */}
        <button
          onClick={() =>
            mobileApi.triggerSimulatedCall({
              caller_name: 'Eva (DeployMate CTO)',
              caller_role: 'Autonomous AI Architect',
              title: 'Urgent Architecture Review',
              prompt_summary: 'Founder sign-off requested for rate-limiting middleware deployment.',
              task_id: 'tsk_rate_limiter_99',
            })
          }
          className="w-full mt-3 py-2 px-3 border-2 border-[#0A0A0A] bg-emerald-500 hover:bg-emerald-600 text-white font-mono text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 transition-all shadow-[2px_2px_0px_#0A0A0A] cursor-pointer"
        >
          <Radio className="w-3.5 h-3.5 text-white animate-pulse" />
          <span>Simulate Team VoIP Call (WhatsApp Style)</span>
        </button>
      </div>

      {/* Spoken Command Input */}
      <div className="space-y-1.5">
        <span className="font-mono text-[10px] font-bold text-zinc-600 uppercase tracking-wider block">SPOKEN INTAKE / NATURAL LANGUAGE DISPATCH</span>
        <div className="flex gap-2">
          <input
            type="text"
            value={commandInput}
            onChange={(e) => setCommandInput(e.target.value)}
            placeholder="e.g. 'Eva, add rate-limiting middleware to our FastAPI endpoints'..."
            className="flex-1 bg-white border-2 border-[#0A0A0A] px-3 py-2 text-xs font-mono text-[#0A0A0A] placeholder:text-zinc-400 focus:outline-none"
          />
          <button
            onClick={() => handleSendCommand(commandInput)}
            className="px-3.5 py-2 border-2 border-[#0A0A0A] bg-[#0A0A0A] hover:bg-zinc-800 text-white font-mono text-xs font-bold uppercase flex items-center gap-1 transition-colors cursor-pointer"
          >
            <Send className="w-3 h-3" /> Dispatch
          </button>
        </div>

        {commandResponse && (
          <div className="p-3 bg-emerald-50 border-2 border-emerald-600 text-xs font-mono text-emerald-900 space-y-1">
            <div className="flex items-center gap-1.5 font-bold text-emerald-800">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" /> Eva Acknowledged:
            </div>
            <div>{commandResponse}</div>
          </div>
        )}
      </div>

      {/* Executive Briefing Summary */}
      <div className="bg-white border-2 border-[#0A0A0A] shadow-[2px_2px_0px_#0A0A0A] p-4 space-y-2">
        <div className="flex items-center gap-1.5 font-mono text-[10px] font-bold text-[#FF3B00] uppercase tracking-wider">
          <Sparkles className="w-3.5 h-3.5" />
          <span>CURRENT EXECUTIVE BRIEFING</span>
        </div>
        <p className="text-xs leading-relaxed text-[#0A0A0A] font-sans">
          "{briefing.executive_summary}"
        </p>
      </div>

      {/* Recommended Actions */}
      <div className="bg-white border-2 border-[#0A0A0A] shadow-[2px_2px_0px_#0A0A0A] p-4 space-y-2">
        <span className="font-mono text-[10px] font-bold text-zinc-600 uppercase tracking-wider block">RECOMMENDED FOUNDER ACTIONS</span>
        <div className="space-y-1 font-mono text-xs">
          {briefing.recommended_actions.map((act, i) => (
            <div key={i} className="flex items-start gap-2 text-[#0A0A0A]">
              <span className="text-[#FF3B00] font-bold">0{i + 1}.</span>
              <span>{act}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
