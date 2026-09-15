import React, { useState, useEffect } from 'react';
import { PhoneCall, Radio, ShieldCheck, Volume2, Video, ArrowRight, RefreshCw, AlertCircle } from 'lucide-react';
import { MeetingSetupScreenData, ScreenId } from '../types';
import { desktopApi } from '../api/client';

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
      const data = await desktopApi.getMeetingSetup(room);
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
      onNavigate('EvaMeeting');
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8 bg-white text-[#0A0A0A] font-sans">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-4 flex justify-between items-end">
        <div>
          <span className="text-xs font-mono tracking-widest uppercase bg-[#0A0A0A] text-white px-2 py-0.5 font-bold">
            Screen M-05 • MC-07
          </span>
          <h1 className="text-3xl font-bold font-mono tracking-tight mt-2">
            MEETING SETUP & WEBRTC SFU
          </h1>
          <p className="text-sm text-neutral-600 mt-1">
            LiveKit WebRTC gateway configuration, room token provisioning, and hardware audio pipeline.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs">
          <button
            onClick={() => fetchSetup(roomName)}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[#0A0A0A] hover:bg-neutral-100 uppercase font-bold text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 border-2 border-rose-800 bg-rose-50 text-rose-950 font-mono text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-800 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Left Column: Room & Identity Controls */}
        <div className="space-y-6">
          <form onSubmit={handleRefresh} className="border border-[#0A0A0A] p-6 space-y-4 bg-neutral-50">
            <div className="flex items-center gap-2 border-b border-neutral-300 pb-2">
              <PhoneCall className="w-4 h-4 text-[#E6391E]" />
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider">
                Meeting Parameters (Production API)
              </h2>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div>
                <label className="block text-neutral-600 uppercase text-[10px] mb-1 font-bold">
                  Room Identifier
                </label>
                <input
                  type="text"
                  value={roomName}
                  onChange={(e) => setRoomName(e.target.value)}
                  className="w-full border border-[#0A0A0A] bg-white px-3 py-2 text-xs font-mono font-bold"
                  placeholder="Room ID"
                />
              </div>

              <div>
                <label className="block text-neutral-600 uppercase text-[10px] mb-1 font-bold">
                  Participant Identity
                </label>
                <div className="p-2 bg-white border border-neutral-300 text-neutral-800 font-mono">
                  {setupData?.participant_identity || (isLoading ? 'Deriving principal...' : '---')}
                </div>
              </div>

              <div>
                <label className="block text-neutral-600 uppercase text-[10px] mb-1 font-bold">
                  LiveKit SFU Gateway
                </label>
                <div className="p-2 bg-white border border-neutral-300 text-neutral-800 font-mono break-all text-[11px]">
                  {setupData?.livekit_url || (isLoading ? 'Loading endpoint...' : '---')}
                </div>
              </div>

              <div>
                <label className="block text-neutral-600 uppercase text-[10px] mb-1 font-bold">
                  Provisioned WebRTC Token
                </label>
                <div className="p-2 bg-white border border-neutral-300 text-neutral-800 font-mono text-[11px] truncate">
                  {setupData?.token ? `${setupData.token.slice(0, 16)}••••••••[VERIFIED]` : (isLoading ? 'Provisioning...' : '---')}
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2 bg-[#0A0A0A] text-white hover:bg-neutral-800 font-mono text-xs uppercase font-bold flex items-center justify-center gap-2"
            >
              <span>Sync Production Gateway</span>
            </button>
          </form>
        </div>

        {/* Right Column: Audio Pipeline & Live Session Launch */}
        <div className="space-y-6">
          <div className="border border-[#0A0A0A] p-6 space-y-4">
            <div className="flex items-center gap-2 border-b border-neutral-300 pb-2">
              <Radio className="w-4 h-4 text-[#E6391E]" />
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider">
                Telemetry & Audio Spec
              </h2>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="flex justify-between items-center p-2.5 border border-neutral-200 bg-neutral-50">
                <span className="text-neutral-600">Audio Codec</span>
                <span className="font-bold uppercase">{setupData?.audio_codec || (isLoading ? '...' : '---')}</span>
              </div>
              <div className="flex justify-between items-center p-2.5 border border-neutral-200 bg-neutral-50">
                <span className="text-neutral-600">Sample Rate</span>
                <span className="font-bold">{setupData?.sample_rate ? `${setupData.sample_rate} Hz` : (isLoading ? '...' : '---')}</span>
              </div>
              <div className="flex justify-between items-center p-2.5 border border-neutral-200 bg-neutral-50">
                <span className="text-neutral-600">Audio Uplink</span>
                <span className="font-bold text-emerald-700 flex items-center gap-1">
                  <Volume2 className="w-3.5 h-3.5" />
                  {setupData?.audio_active ? 'ACTIVE' : 'MUTED'}
                </span>
              </div>
              <div className="flex justify-between items-center p-2.5 border border-neutral-200 bg-neutral-50">
                <span className="text-neutral-600">Gateway Status</span>
                <span className="font-bold text-emerald-800 uppercase flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  {setupData?.status || (isLoading ? 'Connecting...' : '---')}
                </span>
              </div>
            </div>

            <div className="pt-4 border-t border-neutral-200">
              <button
                onClick={handleLaunch}
                className="w-full py-3 bg-[#E6391E] text-white hover:bg-[#c82f17] font-mono text-xs uppercase font-bold flex items-center justify-center gap-2 shadow-md transition-colors"
              >
                <span>Launch Eva Briefing Session</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MeetingSetupScreen;
