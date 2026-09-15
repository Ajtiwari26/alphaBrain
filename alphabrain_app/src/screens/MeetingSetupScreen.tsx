import React, { useState, useEffect } from 'react';
import { PhoneCall, Radio, ShieldCheck, Volume2, ArrowRight, RefreshCw, AlertCircle } from 'lucide-react';
import { MeetingSetupScreenData, ScreenId } from '../types';
import { mobileApi } from '../api/client';

interface Props {
  onNavigate?: (screen: ScreenId) => void;
}

export const MeetingSetupScreen: React.FC<Props> = ({ onNavigate }) => {
  const [setupData, setSetupData] = useState<MeetingSetupScreenData | null>(null);
  const [roomName, setRoomName] = useState('alphabrain-executive-briefing');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSetup = async (room: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await mobileApi.getMeetingSetup(room);
      setSetupData(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch production meeting setup');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSetup(roomName);
  }, []);

  const handleRefresh = (e: React.FormEvent) => {
    e.preventDefault();
    fetchSetup(roomName);
  };

  const handleLaunch = () => {
    if (onNavigate) {
      onNavigate('eva_meeting');
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] p-4 font-sans space-y-6">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          LIVEKIT WEBRTC PIPELINE
        </span>
        <div className="flex items-center justify-between mt-1">
          <h2 className="text-2xl font-headline font-bold text-[#0A0A0A]">
            Meeting Setup
          </h2>
          <span className="font-mono text-[10px] font-bold px-2 py-0.5 border border-[#0A0A0A] bg-black text-white">
            {setupData?.status ? setupData.status.toUpperCase() : (isLoading ? 'SYNCING...' : 'OFFLINE')}
          </span>
        </div>
      </div>

      {error && (
        <div className="p-3 border border-rose-800 bg-rose-50 text-rose-950 font-mono text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-800 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleRefresh} className="space-y-4 border border-[#0A0A0A] p-4 bg-zinc-50">
        <div className="flex items-center justify-between border-b border-zinc-300 pb-2">
          <div className="flex items-center gap-2">
            <PhoneCall className="w-4 h-4 text-[#E6391E]" />
            <span className="text-xs font-mono font-bold uppercase">Room Configuration</span>
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="text-[11px] font-mono font-bold uppercase border border-[#0A0A0A] px-2 py-0.5 bg-white flex items-center gap-1"
          >
            <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Sync</span>
          </button>
        </div>

        <div className="space-y-2 font-mono text-xs">
          <div>
            <label className="text-[10px] text-zinc-500 block uppercase font-bold">Room Name</label>
            <input
              type="text"
              value={roomName}
              onChange={(e) => setRoomName(e.target.value)}
              className="w-full border border-[#0A0A0A] bg-white p-2 text-xs font-bold"
            />
          </div>

          <div>
            <label className="text-[10px] text-zinc-500 block uppercase font-bold">Authenticated Identity</label>
            <div className="p-2 bg-white border border-zinc-300 text-xs">
              {setupData?.participant_identity || (isLoading ? 'Deriving...' : '---')}
            </div>
          </div>

          <div>
            <label className="text-[10px] text-zinc-500 block uppercase font-bold">LiveKit Gateway</label>
            <div className="p-2 bg-white border border-zinc-300 text-[11px] break-all">
              {setupData?.livekit_url || (isLoading ? 'Connecting...' : '---')}
            </div>
          </div>

          <div>
            <label className="text-[10px] text-zinc-500 block uppercase font-bold">WebRTC Token</label>
            <div className="p-2 bg-white border border-zinc-300 text-[11px] truncate">
              {setupData?.token ? `${setupData.token.slice(0, 16)}••••••••[VERIFIED]` : (isLoading ? 'Provisioning...' : '---')}
            </div>
          </div>
        </div>
      </form>

      <div className="border border-[#0A0A0A] p-4 space-y-3 font-mono text-xs">
        <div className="flex items-center gap-2 border-b border-zinc-300 pb-2">
          <Radio className="w-4 h-4 text-[#E6391E]" />
          <span className="font-bold uppercase text-xs">Media Telemetry</span>
        </div>
        <div className="flex justify-between py-1 border-b border-zinc-200">
          <span className="text-zinc-600">Codec</span>
          <span className="font-bold">{setupData?.audio_codec?.toUpperCase() || (isLoading ? '...' : '---')}</span>
        </div>
        <div className="flex justify-between py-1 border-b border-zinc-200">
          <span className="text-zinc-600">Sample Rate</span>
          <span className="font-bold">{setupData?.sample_rate ? `${setupData.sample_rate} Hz` : (isLoading ? '...' : '---')}</span>
        </div>
        <div className="flex justify-between py-1">
          <span className="text-zinc-600">Hardware Uplink</span>
          <span className="font-bold text-emerald-700 flex items-center gap-1">
            <Volume2 className="w-3.5 h-3.5" />
            {setupData?.audio_active ? 'READY' : 'MUTED'}
          </span>
        </div>
      </div>

      <div className="pt-2">
        <button
          onClick={handleLaunch}
          className="w-full py-3 bg-[#E6391E] text-white font-mono text-xs uppercase font-bold flex items-center justify-center gap-2 shadow hover:bg-[#c82f17] transition-colors"
        >
          <span>Connect to Live Session</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default MeetingSetupScreen;
