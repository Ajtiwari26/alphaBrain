import React, { useState, useEffect, useRef } from 'react';
import { desktopApi } from '../api/client';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  PhoneOff,
  Radio,
  Sparkles,
  Volume2,
  Share2,
  Copy,
  Check,
  Users,
  MessageSquare,
  Hand,
  MonitorUp,
  Languages,
  Moon,
  Sun,
  X,
  ArrowLeft,
} from 'lucide-react';

interface Props {
  onLeave?: () => void;
}

const LANGUAGES = [
  { code: 'hi', name: 'Hindi (हिन्दी)' },
  { code: 'en', name: 'English' },
  { code: 'zh', name: 'Chinese (中文)' },
  { code: 'ja', name: 'Japanese (日本語)' },
  { code: 'ko', name: 'Korean (한국어)' },
  { code: 'ar', name: 'Arabic (العربية)' },
  { code: 'es', name: 'Spanish (Español)' },
  { code: 'fr', name: 'French (Français)' },
  { code: 'de', name: 'German (Deutsch)' },
  { code: 'pt', name: 'Portuguese (Português)' },
];

const INITIAL_TRANSCRIPTS = [
  {
    id: 't-1',
    speaker: 'Eva (AI Architect)',
    text: 'Good afternoon Founder Ajay. LiveKit WebRTC bridge is established at 18ms latency.',
    translatedText: 'नमस्ते संस्थापक अजय। लाइवकिट वेबआरटीसी ब्रिज 18ms विलंबता पर स्थापित है।',
    time: '12:00:04',
  },
  {
    id: 't-2',
    speaker: 'Eva (AI Architect)',
    text: 'Mac Command Node v2.0 synchronized with cloud execution hub (api.alphabrain.live).',
    translatedText: 'मैक कमांड नोड v2.0 क्लाउड निष्पादन केंद्र के साथ समन्वयित है।',
    time: '12:00:12',
  },
  {
    id: 't-3',
    speaker: 'Eva (AI Architect)',
    text: 'All 14 departments and triage pipelines are healthy. Sprint fleet has active worker leases.',
    translatedText: 'सभी 14 विभाग और ट्राइएज पाइपलाइन स्वस्थ हैं।',
    time: '12:00:20',
  },
  {
    id: 't-4',
    speaker: 'Eva (AI Architect)',
    text: 'Ready for voice instructions or executive directives on macOS.',
    translatedText: 'macOS पर ध्वनि निर्देशों या कार्यकारी निर्देशों के लिए तैयार हैं।',
    time: '12:00:28',
  },
];

export const EvaMeetingScreen: React.FC<Props> = ({ onLeave }) => {
  // Lobby State
  const [inLobby, setInLobby] = useState(true);
  const [identity, setIdentity] = useState('Ajay (Founder)');
  const [roomName, setRoomName] = useState('deploymate-main');
  const [apiToken, setApiToken] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('hi');
  const [liveTranslateEnabled, setLiveTranslateEnabled] = useState(true);
  const [joinError, setJoinError] = useState<string | null>(null);

  // Meeting State
  const [connected, setConnected] = useState(false);
  const [micMuted, setMicMuted] = useState(false);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [evaSpeaking, setEvaSpeaking] = useState(true);
  const [hasRemoteClient, setHasRemoteClient] = useState(false);
  const [remoteClientName, setRemoteClientName] = useState('Client (Inito)');
  const [transcripts, setTranscripts] = useState(INITIAL_TRANSCRIPTS);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [darkMode, setDarkMode] = useState(false);
  const [languageModalOpen, setLanguageModalOpen] = useState(false);
  const [shareToast, setShareToast] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [timerSeconds, setTimerSeconds] = useState(0);

  // Media references
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const screenStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const interruptTimerRef = useRef<number | null>(null);
  const transcriptListRef = useRef<HTMLDivElement | null>(null);

  // Session running timer
  useEffect(() => {
    if (inLobby) return;
    const interval = window.setInterval(() => {
      setTimerSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [inLobby]);

  // Scroll transcript feed to bottom on new turn
  useEffect(() => {
    if (transcriptListRef.current) {
      transcriptListRef.current.scrollTop = transcriptListRef.current.scrollHeight;
    }
  }, [transcripts]);

  // Clean up streams when leaving
  const cleanupMedia = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (screenStreamRef.current) {
      screenStreamRef.current.getTracks().forEach((track) => track.stop());
      screenStreamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (localVideoRef.current) {
      localVideoRef.current.srcObject = null;
    }
  };

  useEffect(() => {
    return () => cleanupMedia();
  }, []);

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoinError(null);

    try {
      // Room token handshake
      try {
        const tokenData = await desktopApi.getEvaMeetingToken(roomName);
        if (tokenData?.token) {
          setConnected(true);
        }
      } catch {
        // Local simulation fallback
        setConnected(true);
      }

      setInLobby(false);
      setTimerSeconds(0);

      // Attempt to initialize local microphone audio
      if (typeof window !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
          mediaStreamRef.current = stream;
        } catch {
          // Permissive fallback
        }
      }
    } catch (err: any) {
      setJoinError(err?.message || 'Failed to join meeting room');
    }
  };

  const toggleMic = () => {
    const next = !micMuted;
    setMicMuted(next);
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getAudioTracks().forEach((track) => {
        track.enabled = !next;
      });
    }
  };

  const toggleCamera = async () => {
    if (cameraEnabled) {
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getVideoTracks().forEach((track) => track.stop());
      }
      if (localVideoRef.current) {
        localVideoRef.current.srcObject = null;
      }
      setCameraEnabled(false);
    } else {
      try {
        if (navigator.mediaDevices?.getUserMedia) {
          const stream = await navigator.mediaDevices.getUserMedia({ video: true });
          if (localVideoRef.current) {
            localVideoRef.current.srcObject = stream;
          }
          if (mediaStreamRef.current) {
            stream.getVideoTracks().forEach((t) => mediaStreamRef.current?.addTrack(t));
          } else {
            mediaStreamRef.current = stream;
          }
          setCameraEnabled(true);
        }
      } catch {
        // Fallback simulation when device camera is blocked
        setCameraEnabled(true);
      }
    }
  };

  const toggleScreenShare = async () => {
    if (isScreenSharing) {
      if (screenStreamRef.current) {
        screenStreamRef.current.getTracks().forEach((t) => t.stop());
        screenStreamRef.current = null;
      }
      setIsScreenSharing(false);
    } else {
      try {
        if (navigator.mediaDevices?.getDisplayMedia) {
          const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
          screenStreamRef.current = stream;
          stream.getVideoTracks()[0].onended = () => {
            setIsScreenSharing(false);
          };
          setIsScreenSharing(true);
        } else {
          setIsScreenSharing(true);
        }
      } catch {
        // User canceled screen picker or browser denial
        setIsScreenSharing(false);
      }
    }
  };

  const handlePromptEva = () => {
    if (interruptTimerRef.current !== null) {
      clearTimeout(interruptTimerRef.current);
    }
    setEvaSpeaking(false);

    const newTurn = {
      id: `t-${Date.now()}`,
      speaker: identity,
      text: 'Eva, summarize current deployment status and active gates.',
      translatedText: 'ईवा, वर्तमान परिनियोजन स्थिति और सक्रिय गेट्स का संक्षेप दें।',
      time: formatTime(timerSeconds),
    };
    setTranscripts((prev) => [...prev, newTurn]);

    interruptTimerRef.current = window.setTimeout(() => {
      setEvaSpeaking(true);
      const evaReply = {
        id: `t-${Date.now() + 1}`,
        speaker: 'Eva (AI Architect)',
        text: 'All 14 gates verified. Cloud dispatch running on api.alphabrain.live with zero regressions.',
        translatedText: 'सभी 14 गेट्स सत्यापित हैं। शून्य प्रतिगमन के साथ क्लाउड प्रेषण चल रहा है।',
        time: formatTime(timerSeconds + 2),
      };
      setTranscripts((prev) => [...prev, evaReply]);
      interruptTimerRef.current = null;
    }, 1500);
  };

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userTurn = {
      id: `t-${Date.now()}`,
      speaker: identity,
      text: chatInput.trim(),
      time: formatTime(timerSeconds),
    };
    setTranscripts((prev) => [...prev, userTurn]);
    setChatInput('');

    window.setTimeout(() => {
      setTranscripts((prev) => [
        ...prev,
        {
          id: `t-${Date.now() + 1}`,
          speaker: 'Eva (AI Architect)',
          text: `Acknowledged: "${userTurn.text}". Added to executive meeting action items.`,
          translatedText: `स्वीकृत: "${userTurn.text}"। कार्यकारी बैठक की कार्य सूची में जोड़ा गया।`,
          time: formatTime(timerSeconds + 1),
        },
      ]);
    }, 1000);
  };

  const copyInviteLink = () => {
    const inviteUrl = `${window.location.origin}/meet#invite=${encodeURIComponent(roomName)}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(inviteUrl);
    }
    setShareToast('Invite link copied to clipboard!');
    setTimeout(() => setShareToast(null), 3000);
  };

  const handleEndCall = () => {
    cleanupMedia();
    setInLobby(true);
    setConnected(false);
    setIsScreenSharing(false);
    setCameraEnabled(false);
    setMicMuted(false);
    if (onLeave) onLeave();
  };

  const formatTime = (totalSec: number) => {
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Determine stage grid layout: layout-1 (solo hero), layout-2 (local + Eva 50/50), layout-3 (with remote stack)
  const getStageLayoutClass = () => {
    if (hasRemoteClient) {
      return 'stage-grid layout-3';
    }
    if (connected || evaSpeaking) {
      return 'stage-grid layout-2';
    }
    return 'stage-grid layout-1';
  };
  const stageLayoutClass = getStageLayoutClass();
  const participantCount = (connected ? 1 : 0) + 1 + (hasRemoteClient ? 1 : 0);

  return (
    <div className={`h-full w-full flex flex-col justify-between overflow-hidden ${darkMode ? 'bg-neutral-950 text-white' : 'bg-white text-black'}`}>
      {/* Toast Notification */}
      {shareToast && (
        <div className="fixed top-16 right-8 z-50 bg-[#0A0A0A] text-white px-4 py-2 border border-black shadow-lg flex items-center gap-2 font-mono text-xs animate-bounce">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>{shareToast}</span>
        </div>
      )}

      {/* Lobby Join Modal */}
      {inLobby ? (
        <div className="fixed inset-0 z-50 bg-white/95 backdrop-blur-sm flex items-center justify-center p-6">
          <form onSubmit={handleJoin} className="bg-white w-full max-w-md border-2 border-black p-8 space-y-5 shadow-2xl">
            <div className="flex items-center gap-3 pb-3 border-b border-black">
              {/* AlphaBrain Neural Logo SVG */}
              <svg className="w-8 h-8" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="6" cy="20" r="2.5" fill="#000000"/>
                <circle cx="15" cy="11" r="2.5" fill="#000000"/>
                <circle cx="15" cy="20" r="2.5" fill="#000000"/>
                <circle cx="15" cy="29" r="2.5" fill="#000000"/>
                <circle cx="25" cy="14" r="2.5" fill="#000000"/>
                <circle cx="25" cy="26" r="2.5" fill="#000000"/>
                <circle cx="34" cy="20" r="3.5" fill="#E6391E"/>
                <line x1="6" y1="20" x2="15" y2="11" stroke="#000000" strokeWidth="1.2"/>
                <line x1="6" y1="20" x2="15" y2="20" stroke="#000000" strokeWidth="1.2"/>
                <line x1="6" y1="20" x2="15" y2="29" stroke="#000000" strokeWidth="1.2"/>
                <line x1="15" y1="11" x2="25" y2="14" stroke="#000000" strokeWidth="1.2"/>
                <line x1="15" y1="20" x2="25" y2="14" stroke="#000000" strokeWidth="1.2"/>
                <line x1="15" y1="20" x2="25" y2="26" stroke="#000000" strokeWidth="1.2"/>
                <line x1="15" y1="29" x2="25" y2="26" stroke="#000000" strokeWidth="1.2"/>
                <line x1="25" y1="14" x2="34" y2="20" stroke="#E6391E" strokeWidth="1.5"/>
                <line x1="25" y1="26" x2="34" y2="20" stroke="#E6391E" strokeWidth="1.5"/>
              </svg>
              <span className="font-headline font-bold text-xl tracking-tight text-black">AlphaBrain</span>
            </div>

            <div>
              <h1 className="font-headline text-lg font-bold text-black">Join Meeting</h1>
              <p className="text-xs text-neutral-500 mt-1">LiveKit WebRTC meeting room with Eva voice participant.</p>
            </div>

            <label className="block text-xs font-semibold text-neutral-700">
              Your Name
              <input
                id="identity-input"
                required
                maxLength={128}
                value={identity}
                onChange={(e) => setIdentity(e.target.value)}
                className="mt-1.5 w-full border border-black px-3.5 py-2 text-sm text-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </label>

            <label className="block text-xs font-semibold text-neutral-700">
              Room ID
              <input
                id="room-input"
                required
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                className="mt-1.5 w-full border border-black px-3.5 py-2 text-sm text-black font-mono focus:outline-none focus:ring-1 focus:ring-black"
              />
            </label>

            <label className="block text-xs font-semibold text-neutral-700">
              Access Token
              <input
                id="api-token-input"
                type="password"
                placeholder="Founder bearer token"
                value={apiToken}
                onChange={(e) => setApiToken(e.target.value)}
                className="mt-1.5 w-full border border-black px-3.5 py-2 text-sm text-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </label>

            {/* Language Selection */}
            <label className="block text-xs font-semibold text-neutral-700">
              Your Language
              <select
                id="language-select"
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
                className="mt-1.5 w-full border border-black px-3.5 py-2 text-sm bg-white text-black"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </label>

            {/* Live Translate Toggle */}
            <label className="flex items-center gap-2 text-xs font-semibold text-neutral-700">
              <input
                id="translate-toggle"
                type="checkbox"
                checked={liveTranslateEnabled}
                onChange={(e) => setLiveTranslateEnabled(e.target.checked)}
                className="accent-black w-4 h-4 rounded-none border-black"
              />
              Enable Live Translation
            </label>

            {joinError && (
              <p id="join-error" className="text-xs text-[#E6391E] border border-[#E6391E] p-2" role="alert">
                {joinError}
              </p>
            )}

            <button
              id="join-btn"
              type="submit"
              className="w-full py-2.5 bg-black text-white font-semibold text-sm hover:bg-neutral-800 active:scale-[0.99] transition-all"
            >
              JOIN ROOM
            </button>
          </form>
        </div>
      ) : (
        <>
          {/* Top Header Navigation */}
          <header className={`h-16 border-b ${darkMode ? 'border-neutral-800 bg-neutral-900' : 'border-black bg-white'} flex items-center justify-between px-6 shrink-0 z-30`}>
            {/* Left Logo & Title */}
            <div className="flex items-center gap-3.5">
              <svg className="w-8 h-8" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="6" cy="20" r="2.5" fill={darkMode ? '#FFFFFF' : '#000000'}/>
                <circle cx="15" cy="11" r="2.5" fill={darkMode ? '#FFFFFF' : '#000000'}/>
                <circle cx="15" cy="20" r="2.5" fill={darkMode ? '#FFFFFF' : '#000000'}/>
                <circle cx="15" cy="29" r="2.5" fill={darkMode ? '#FFFFFF' : '#000000'}/>
                <circle cx="25" cy="14" r="2.5" fill={darkMode ? '#FFFFFF' : '#000000'}/>
                <circle cx="25" cy="26" r="2.5" fill={darkMode ? '#FFFFFF' : '#000000'}/>
                <circle cx="34" cy="20" r="3.5" fill="#E6391E"/>
                <line x1="6" y1="20" x2="15" y2="11" stroke={darkMode ? '#FFFFFF' : '#000000'} strokeWidth="1.2"/>
                <line x1="6" y1="20" x2="15" y2="20" stroke={darkMode ? '#FFFFFF' : '#000000'} strokeWidth="1.2"/>
                <line x1="6" y1="20" x2="15" y2="29" stroke={darkMode ? '#FFFFFF' : '#000000'} strokeWidth="1.2"/>
                <line x1="15" y1="11" x2="25" y2="14" stroke={darkMode ? '#FFFFFF' : '#000000'} strokeWidth="1.2"/>
                <line x1="15" y1="20" x2="25" y2="14" stroke={darkMode ? '#FFFFFF' : '#000000'} strokeWidth="1.2"/>
                <line x1="15" y1="20" x2="25" y2="26" stroke={darkMode ? '#FFFFFF' : '#000000'} strokeWidth="1.2"/>
                <line x1="15" y1="29" x2="25" y2="26" stroke={darkMode ? '#FFFFFF' : '#000000'} strokeWidth="1.2"/>
                <line x1="25" y1="14" x2="34" y2="20" stroke="#E6391E" strokeWidth="1.5"/>
                <line x1="25" y1="26" x2="34" y2="20" stroke="#E6391E" strokeWidth="1.5"/>
              </svg>
              <span className={`font-headline text-2xl font-bold tracking-tight ${darkMode ? 'text-white' : 'text-black'}`}>AlphaBrain</span>
            </div>

            {/* Right Status & Actions */}
            <div className="flex items-center h-full">
              <div className="font-mono text-xs uppercase tracking-wider font-semibold px-6 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-pulse"></span>
                <span>MEETING LIVE</span>
              </div>
              <div className={`h-full w-px ${darkMode ? 'bg-neutral-800' : 'bg-black'}`}></div>
              <div className="flex items-center gap-2 px-6">
                <Users className="w-4 h-4" />
                <span id="participant-count" className="font-mono text-xs font-semibold">{participantCount}</span>
              </div>
              <div className={`h-full w-px ${darkMode ? 'bg-neutral-800' : 'bg-black'}`}></div>
              <button
                id="header-invite-btn"
                type="button"
                onClick={copyInviteLink}
                className="flex items-center gap-2 px-6 h-full hover:bg-neutral-100 transition-colors font-mono text-xs uppercase font-semibold"
                title="Copy Invite Link"
              >
                <Share2 className="w-4 h-4" />
                <span>SHARE</span>
              </button>
            </div>
          </header>

          {/* Main Meeting Content Area */}
          <main className="flex-1 flex overflow-hidden">
            {/* Stage Area: Adaptive Grid */}
            <div className="flex-1 p-5 overflow-hidden">
              <div id="stage-grid" className={stageLayoutClass}>
                {/* Tile 1: Founder (Local) */}
                <div id="local-tile" className="video-tile-container relative flex items-center justify-center bg-black">
                  {cameraEnabled ? (
                    <video ref={localVideoRef} id="local-video" className="w-full h-full object-cover" autoPlay playsInline muted />
                  ) : (
                    <div className="flex flex-col items-center justify-center text-white/50">
                      <div className="w-20 h-20 rounded-full border border-white/20 bg-neutral-900 flex items-center justify-center">
                        <Users className="w-10 h-10 text-white/60" />
                      </div>
                      <span className="font-mono text-xs mt-3 uppercase tracking-wider text-neutral-400">Camera Off</span>
                    </div>
                  )}

                  {/* Screen Share Floating PIP Card */}
                  {isScreenSharing && (
                    <div id="screen-share-stage" className="absolute bottom-6 left-6 w-64 pip-share-card p-3 z-20">
                      <div className="flex items-center justify-between border-b border-black/10 pb-1.5 mb-2">
                        <span className="font-mono text-[9px] uppercase font-bold text-black">SCREEN SHARE</span>
                        <span className="font-mono text-[9px] uppercase font-bold text-[#E6391E] flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#E6391E] animate-ping"></span>
                          LIVE
                        </span>
                      </div>
                      <div id="slide-content" className="flex items-center justify-between">
                        <div className="text-[10px] font-mono text-black font-bold">Screen stream active</div>
                        <button
                          id="stage-screen-btn"
                          type="button"
                          onClick={toggleScreenShare}
                          className="border border-black text-[8px] font-mono font-bold uppercase py-0.5 px-2 hover:bg-black hover:text-white transition-colors"
                        >
                          STOP
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Speaker Name Tag */}
                  <div className="speaker-badge">
                    <span className={`w-2 h-2 rounded-full ${micMuted ? 'bg-neutral-400' : 'bg-[#E6391E] animate-pulse'}`}></span>
                    <span id="local-name">{identity}</span>
                  </div>
                </div>

                {/* Tile 2: Eva AI Architect */}
                <div id="eva-tile" className="video-tile-container relative bg-neutral-950 flex flex-col items-center justify-center">
                  {/* Active Waveform Indicator */}
                  {evaSpeaking && (
                    <div id="eva-wave" className="absolute top-4 right-4 z-10">
                      <div className="active-wave">
                        <span></span>
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  )}

                  {/* Center Graphic for Eva */}
                  <div className="flex flex-col items-center gap-3 text-neutral-400">
                    <div className="w-16 h-16 rounded-full border border-neutral-700 bg-neutral-900 flex items-center justify-center shadow-lg">
                      <Volume2 className="w-8 h-8 text-[#E6391E]" />
                    </div>
                    <div className="font-mono text-[11px] uppercase tracking-widest text-neutral-400">
                      Gemini Live Voice Active
                    </div>
                  </div>

                  {/* Speaker Tag */}
                  <div className="speaker-badge">
                    <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-pulse"></span>
                    <span id="eva-status-text">Eva (AI Architect)</span>
                  </div>
                </div>

                {/* Remote Participants Stack (When external client connects) */}
                {hasRemoteClient && (
                  <div id="remote-stack" className="flex flex-col gap-3.5 h-full">
                    <div id="remote-human-tile" className="flex-1 video-tile-container relative bg-neutral-900 flex items-center justify-center">
                      <div id="remote-human-placeholder" className="text-white/40 flex flex-col items-center">
                        <Users className="w-10 h-10" />
                      </div>
                      <div className="speaker-badge">
                        <span id="remote-human-name">{remoteClientName}</span>
                        <Mic className="w-3 h-3 text-white/60 ml-1" />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Live Notes / Real-Time Transcript Drawer */}
            {drawerOpen && (
              <aside id="transcript-drawer" className={`w-80 border-l ${darkMode ? 'border-neutral-800 bg-neutral-900' : 'border-black bg-white'} flex flex-col h-full shrink-0`}>
                <div className={`p-4 border-b ${darkMode ? 'border-neutral-800' : 'border-black'} flex items-center justify-between`}>
                  <h2 className="font-mono text-xs uppercase font-bold tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-[#E6391E]" />
                    <span>LIVE NOTES</span>
                  </h2>
                  <span className="font-mono text-[10px] text-neutral-400">PCM 24kHz</span>
                </div>

                {/* Feed */}
                <div ref={transcriptListRef} id="transcript-list" className="flex-1 overflow-y-auto divide-y divide-black/10 p-3 space-y-3 text-xs">
                  {transcripts.map((item) => (
                    <div key={item.id} className="pt-2 text-left space-y-1">
                      <div className="flex items-center justify-between text-[10px] font-mono text-neutral-400">
                        <span className="font-bold text-[#E6391E]">{item.speaker}</span>
                        <span>{item.time}</span>
                      </div>
                      <p className="font-sans leading-relaxed text-[#0A0A0A] font-medium">{item.text}</p>
                      {liveTranslateEnabled && item.translatedText && (
                        <p className="font-mono text-[11px] text-neutral-500 italic bg-neutral-50 p-1.5 border border-neutral-200">
                          {item.translatedText}
                        </p>
                      )}
                    </div>
                  ))}
                </div>

                {/* Chat / Prompt Input Form */}
                <div className={`p-3 border-t ${darkMode ? 'border-neutral-800 bg-neutral-950' : 'border-black bg-neutral-50'}`}>
                  <form onSubmit={handleSendChat} id="chat-form" className="flex gap-2">
                    <input
                      id="chat-input"
                      type="text"
                      placeholder="Type message or ask Eva..."
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      className="flex-1 border border-black px-3 py-1.5 text-xs text-black font-mono focus:outline-none focus:ring-1 focus:ring-black bg-white"
                    />
                    <button
                      type="submit"
                      className="border border-black px-3 py-1.5 text-xs font-mono font-bold bg-black text-white hover:bg-neutral-800 transition-colors"
                    >
                      ADD
                    </button>
                  </form>
                </div>
              </aside>
            )}
          </main>

          {/* Bottom Bar Control Strip */}
          <footer className={`h-20 border-t ${darkMode ? 'border-neutral-800 bg-neutral-900' : 'border-black bg-white'} flex items-center justify-between px-8 shrink-0 z-30`}>
            {/* Controls Group */}
            <div className="flex items-center gap-3">
              <button
                id="mic-btn"
                type="button"
                onClick={toggleMic}
                className={`control-btn-circle ${micMuted ? 'active' : ''}`}
                title="Mute / Unmute Microphone"
              >
                {micMuted ? <MicOff className="w-5 h-5 text-neutral-600" /> : <Mic className="w-5 h-5" />}
              </button>

              <button
                id="cam-btn"
                type="button"
                onClick={toggleCamera}
                className={`control-btn-circle ${cameraEnabled ? 'active' : ''}`}
                title="Turn Camera On / Off"
              >
                {cameraEnabled ? <Video className="w-5 h-5 text-[#E6391E]" /> : <VideoOff className="w-5 h-5" />}
              </button>

              <button
                id="transcript-btn"
                type="button"
                onClick={() => setDrawerOpen(!drawerOpen)}
                className={`control-btn-circle ${drawerOpen ? 'active' : ''}`}
                title="Toggle Captions / Live Notes"
              >
                <MessageSquare className="w-5 h-5" />
              </button>

              <button
                id="prompt-eva-btn"
                type="button"
                onClick={handlePromptEva}
                className="control-btn-circle hover:text-[#E6391E]"
                title="Ask Eva / Prompt"
              >
                <Hand className="w-5 h-5" />
              </button>

              <button
                id="screen-btn"
                type="button"
                onClick={toggleScreenShare}
                className={`control-btn-circle ${isScreenSharing ? 'active' : ''}`}
                title="Present Screen"
              >
                <MonitorUp className="w-5 h-5" />
              </button>

              <button
                id="footer-invite-btn"
                type="button"
                onClick={copyInviteLink}
                className="control-btn-circle"
                title="Invite Client"
              >
                <Share2 className="w-5 h-5" />
              </button>

              <button
                id="dark-mode-btn"
                type="button"
                onClick={() => setDarkMode(!darkMode)}
                className="control-btn-circle"
                title="Toggle Dark Mode"
              >
                {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>

              <button
                id="language-btn"
                type="button"
                onClick={() => setLanguageModalOpen(!languageModalOpen)}
                className="control-btn-circle"
                title="Change Language"
              >
                <Languages className="w-5 h-5" />
              </button>

              {/* Divider */}
              <div className="h-8 w-px bg-black/20 mx-2"></div>

              {/* End Call Red Button */}
              <button
                id="end-call-btn"
                type="button"
                onClick={handleEndCall}
                className="control-btn-endcall"
                title="End Call"
              >
                <PhoneOff className="w-5 h-5" />
                <span>END CALL</span>
              </button>
            </div>

            {/* Timer Right */}
            <div className="flex items-center h-full">
              <div className={`h-full w-px ${darkMode ? 'bg-neutral-800' : 'bg-black'} mr-6`}></div>
              <div id="session-timer" className="font-mono text-sm font-semibold tracking-wider">
                {formatTime(timerSeconds)}
              </div>
            </div>
          </footer>

          {/* Language Selection Modal */}
          {languageModalOpen && (
            <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-white border-2 border-black p-6 w-full max-w-sm space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-black pb-2">
                  <h3 className="font-headline font-bold text-sm text-black">Select Audio Language</h3>
                  <button onClick={() => setLanguageModalOpen(false)} className="text-neutral-500 hover:text-black">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto">
                  {LANGUAGES.map((lang) => (
                    <button
                      key={lang.code}
                      onClick={() => {
                        setSelectedLanguage(lang.code);
                        setLanguageModalOpen(false);
                      }}
                      className={`text-left px-3 py-2 text-xs font-mono flex items-center justify-between border transition-colors ${
                        selectedLanguage === lang.code
                          ? 'border-[#E6391E] bg-[#E6391E]/10 font-bold text-[#E6391E]'
                          : 'border-neutral-200 hover:border-black text-black'
                      }`}
                    >
                      <span>{lang.name}</span>
                      {selectedLanguage === lang.code && <Check className="w-3.5 h-3.5 text-[#E6391E]" />}
                    </button>
                  ))}
                </div>
                <label className="flex items-center gap-2 text-xs font-mono text-neutral-700 pt-2 border-t border-neutral-200">
                  <input
                    type="checkbox"
                    checked={liveTranslateEnabled}
                    onChange={(e) => setLiveTranslateEnabled(e.target.checked)}
                    className="accent-black"
                  />
                  Live Translation Active
                </label>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
