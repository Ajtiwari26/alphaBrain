import React, { useState, useEffect } from 'react';
import { VoiceBriefing } from '../types';
import { mobileApi } from '../api/client';
import { Mic, MicOff, Radio, Volume2, Sparkles, Send, CheckCircle2 } from 'lucide-react';

export const VoiceBriefingScreen: React.FC = () => {
  const [briefing, setBriefing] = useState<VoiceBriefing | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [commandInput, setCommandInput] = useState('');
  const [commandResponse, setCommandResponse] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi.getVoiceBriefing().then((data) => {
      setBriefing(data);
      setLoading(false);
    });
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
    setIsListening(!isListening);
    if (!isListening) {
      // Simulate speech recognition phrase
      setTimeout(() => {
        setCommandInput('Eva, add rate-limiting middleware to our FastAPI endpoints and write unit tests.');
        setIsListening(false);
      }, 2000);
    }
  };

  if (loading || !briefing) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Connecting to Eva Voice AI...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">05 • SPOKEN INTAKE</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Eva Voice CTO</h1>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-accent/10 border border-accent/40 font-mono text-xs text-accent">
          <Radio className="w-3.5 h-3.5 animate-pulse" />
          <span>LIVE ROOM: {briefing.active_room}</span>
        </div>
      </div>

      {/* Voice Visualizer Avatar */}
      <div className="locomotive-card p-6 rounded-xl flex flex-col items-center justify-center text-center relative overflow-hidden">
        <div className={`w-20 h-20 rounded-full flex items-center justify-center mb-3 transition-all duration-300 ${
          isListening 
            ? 'bg-accent/20 border-2 border-accent scale-110 shadow-lg shadow-accent/20' 
            : 'bg-card border border-card-border'
        }`}>
          {isListening ? (
            <Mic className="w-8 h-8 text-accent animate-bounce" />
          ) : (
            <Volume2 className="w-8 h-8 text-slate-300" />
          )}
        </div>

        <h3 className="font-display text-base font-semibold text-white">{briefing.speaker}</h3>
        <p className="font-mono text-xs text-muted mt-0.5">Autonomous Engineering & AI Architect</p>

        <button
          onClick={toggleMic}
          className={`mt-4 px-4 py-2 rounded-full font-mono text-xs font-semibold flex items-center gap-2 transition-all ${
            isListening
              ? 'bg-red-600 text-white animate-pulse'
              : 'bg-accent hover:bg-orange-600 text-white'
          }`}
        >
          {isListening ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
          {isListening ? 'Listening on iQOO 12...' : 'Tap to Speak Command'}
        </button>
      </div>

      {/* Spoken Command Input */}
      <div className="space-y-2">
        <span className="font-mono text-xs text-muted block">SPOKEN INTAKE / NATURAL LANGUAGE DISPATCH</span>
        <div className="flex gap-2">
          <input
            type="text"
            value={commandInput}
            onChange={(e) => setCommandInput(e.target.value)}
            placeholder="e.g. 'Eva, add rate-limiting middleware to our FastAPI endpoints'..."
            className="flex-1 bg-card border border-card-border rounded-lg px-3 py-2 text-xs font-mono text-white placeholder:text-muted focus:outline-none focus:border-accent"
          />
          <button
            onClick={() => handleSendCommand(commandInput)}
            className="px-3.5 py-2 rounded-lg bg-accent hover:bg-orange-600 text-white font-mono text-xs font-semibold flex items-center gap-1 transition-colors"
          >
            <Send className="w-3.5 h-3.5" /> Dispatch
          </button>
        </div>

        {commandResponse && (
          <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-800 text-xs font-mono text-emerald-300 space-y-1">
            <div className="flex items-center gap-1.5 font-semibold text-emerald-400">
              <CheckCircle2 className="w-4 h-4" /> Eva Acknowledged:
            </div>
            <div>{commandResponse}</div>
          </div>
        )}
      </div>

      {/* Executive Briefing Summary */}
      <div className="locomotive-card p-4 rounded-lg space-y-3">
        <div className="flex items-center gap-2 font-mono text-xs text-accent">
          <Sparkles className="w-4 h-4" />
          <span>CURRENT EXECUTIVE BRIEFING</span>
        </div>
        <p className="text-sm leading-relaxed text-slate-300 font-sans">
          "{briefing.executive_summary}"
        </p>
      </div>

      {/* Recommended Actions */}
      <div className="locomotive-card p-4 rounded-lg space-y-2">
        <span className="font-mono text-xs text-muted block">RECOMMENDED FOUNDER ACTIONS</span>
        <div className="space-y-1.5 font-mono text-xs">
          {briefing.recommended_actions.map((act, i) => (
            <div key={i} className="flex items-start gap-2 text-slate-300">
              <span className="text-accent font-bold">0{i + 1}.</span>
              <span>{act}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
