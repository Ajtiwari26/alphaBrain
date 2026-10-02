import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Room,
  RoomEvent,
  Track,
  VideoPresets,
  RemoteParticipant,
  RemoteTrackPublication,
  RemoteTrack,
} from 'livekit-client';
import {
  acquireMeetingToken,
  parseMeetingInput,
  LIVEKIT_CLOUD_URL,
} from '../utils/livekitToken';
import { getApiBaseUrl } from '../api/client';

interface Props {
  onLeave?: () => void;
}

interface TranscriptEntry {
  id: string;
  speaker: string;
  text: string;
  isEva: boolean;
  time: string;
}

const EVA_IDENTITY = 'eva-cto';
const DEFAULT_ROOM = 'deploymate-main';
const DEFAULT_BACKEND = getApiBaseUrl().replace('/api/v1/mobile', '');
const EVA_TARGET_TOPIC = 'alpha.eva.target';

export const EvaMeetingScreen: React.FC<Props> = ({ onLeave }) => {
  // Navigation / Lobby
  const [inLobby, setInLobby] = useState(true);
  const [lobbyTab, setLobbyTab] = useState<'create' | 'join'>('create');
  const [isConnecting, setIsConnecting] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  // Form Fields
  const [participantName, setParticipantName] = useState('Ajay (Founder)');
  const [roomNameInput, setRoomNameInput] = useState(DEFAULT_ROOM);
  const [joinLinkInput, setJoinLinkInput] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('hi');
  const [translateEnabled, setTranslateEnabled] = useState(true);

  // Active Call State
  const [activeRoomName, setActiveRoomName] = useState('');
  const [activeParticipant, setActiveParticipant] = useState('Ajay (Founder)');
  const [participants, setParticipants] = useState<Map<string, RemoteParticipant>>(new Map());
  const [evaState, setEvaState] = useState<'connected' | 'speaking' | 'listening' | 'reconnecting'>('connected');
  const [isAudioMuted, setIsAudioMuted] = useState(false);
  const [isVideoMuted, setIsVideoMuted] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Chat & Transcript
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [chatMessage, setChatMessage] = useState('');

  // Invite Modal
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteClientName, setInviteClientName] = useState('Client');
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [isGeneratingInvite, setIsGeneratingInvite] = useState(false);
  const [copiedInvite, setCopiedInvite] = useState(false);

  // Session Timer
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // DOM Refs
  const roomRef = useRef<Room | null>(null);
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);
  const chatInputRef = useRef<HTMLInputElement | null>(null);
  const transcriptScrollRef = useRef<HTMLDivElement | null>(null);
  const evaAudioRef = useRef<HTMLAudioElement | null>(null);
  const userManuallyMuted = useRef(false);
  const antiFeedbackTimeout = useRef<NodeJS.Timeout | null>(null);

  // Persistent Dedicated Audio Element (Lifecycle-safe for Android WebView)
  useEffect(() => {
    const el = document.createElement('audio');
    el.autoplay = true;
    el.setAttribute('playsinline', '');
    el.setAttribute('webkit-playsinline', '');
    el.style.display = 'none';
    document.body.appendChild(el);
    evaAudioRef.current = el;
    return () => {
      el.pause();
      el.srcObject = null;
      el.remove();
      if (antiFeedbackTimeout.current) {
        clearTimeout(antiFeedbackTimeout.current);
      }
    };
  }, []);

  // Timer Tick
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (!inLobby && roomRef.current) {
      interval = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [inLobby]);

  const formatTimer = (totalSec: number) => {
    const hrs = String(Math.floor(totalSec / 3600)).padStart(2, '0');
    const mins = String(Math.floor((totalSec % 3600) / 60)).padStart(2, '0');
    const secs = String(totalSec % 60).padStart(2, '0');
    return `${hrs}:${mins}:${secs}`;
  };

  useEffect(() => {
    if (transcriptScrollRef.current) {
      transcriptScrollRef.current.scrollTop = transcriptScrollRef.current.scrollHeight;
    }
  }, [transcripts]);

  // Attach local camera video track
  const attachLocalCamera = useCallback(() => {
    if (!roomRef.current || !localVideoRef.current) return;
    const pub = roomRef.current.localParticipant.getTrackPublication(Track.Source.Camera);
    if (pub?.videoTrack) {
      pub.videoTrack.attach(localVideoRef.current);
    }
  }, []);

  // Wire room events
  const wireRoom = useCallback(
    (room: Room) => {
      room
        .on(RoomEvent.TrackSubscribed, (track: RemoteTrack, publication: RemoteTrackPublication, participant: RemoteParticipant) => {
          if (track.kind === Track.Kind.Video && participant.identity !== EVA_IDENTITY) {
            if (remoteVideoRef.current) {
              track.attach(remoteVideoRef.current);
            }
          } else if (track.kind === Track.Kind.Audio && participant.identity === EVA_IDENTITY) {
            // Eva audio -> persistent dedicated element (INV-M06, lifecycle-safe)
            if (evaAudioRef.current) {
              track.attach(evaAudioRef.current);
            }
          } else if (track.kind === Track.Kind.Audio) {
            const el = track.attach();
            el.autoplay = true;
            document.body.appendChild(el);
          }
        })
        .on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
          track.detach().forEach((el) => el.remove());
        })
        .on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
          setParticipants((prev) => new Map(prev).set(participant.identity, participant));
          if (participant.identity === EVA_IDENTITY) {
            setEvaState('connected');
          }
        })
        .on(RoomEvent.ParticipantDisconnected, (participant: RemoteParticipant) => {
          setParticipants((prev) => {
            const next = new Map(prev);
            next.delete(participant.identity);
            return next;
          });
          if (participant.identity === EVA_IDENTITY) {
            setEvaState('reconnecting');
          }
        })
        .on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
          const evaSpeaking = speakers.some((p) => p.identity === EVA_IDENTITY);
          if (evaSpeaking) {
            setEvaState('speaking');
            // ANTI-FEEDBACK SHIELD (INV-M07): Suppress mic during Eva speech to prevent speaker feedback triggering LiveKit interruption
            if (!userManuallyMuted.current && roomRef.current) {
              if (antiFeedbackTimeout.current) {
                clearTimeout(antiFeedbackTimeout.current);
                antiFeedbackTimeout.current = null;
              }
              const micPub = roomRef.current.localParticipant.getTrackPublication(Track.Source.Microphone);
              if (micPub?.track?.mediaStreamTrack) {
                micPub.track.mediaStreamTrack.enabled = false;
              }
            }
          } else if (room.remoteParticipants.has(EVA_IDENTITY)) {
            setEvaState('listening');
            // ANTI-FEEDBACK SHIELD: Re-enable mic after 200ms debounce
            if (!userManuallyMuted.current && roomRef.current) {
              antiFeedbackTimeout.current = setTimeout(() => {
                const micPub = roomRef.current?.localParticipant.getTrackPublication(Track.Source.Microphone);
                if (micPub?.track?.mediaStreamTrack) {
                  micPub.track.mediaStreamTrack.enabled = true;
                }
              }, 200);
            }
          }
        })
        .on(RoomEvent.TranscriptionReceived, (segments, participant) => {
          const speakerName = participant?.name || participant?.identity || 'Participant';
          const isEva = participant?.identity === EVA_IDENTITY;
          const time = new Date().toTimeString().slice(3, 8);

          segments.forEach((seg) => {
            setTranscripts((prev) => {
              const existingIndex = prev.findIndex((e) => e.id === seg.id);
              if (existingIndex >= 0) {
                const next = [...prev];
                next[existingIndex] = {
                  ...next[existingIndex],
                  text: seg.text,
                };
                return next;
              }
              return [
                ...prev,
                {
                  id: seg.id || `seg-${Date.now()}-${Math.random()}`,
                  speaker: speakerName,
                  text: seg.text,
                  isEva,
                  time,
                },
              ];
            });
          });
        })
        .on(RoomEvent.Disconnected, () => {
          setInLobby(true);
        });
    },
    []
  );

  // Connect & Enter Meeting
  const handleJoinMeeting = async (targetRoom: string, inviteToken?: string) => {
    setIsConnecting(true);
    setJoinError(null);

    try {
      const { token, livekitUrl, roomName: resolvedRoom, identity: resolvedIdentity } = await acquireMeetingToken(
        DEFAULT_BACKEND,
        targetRoom,
        participantName.trim() || 'Ajay (Founder)',
        'founder',
        inviteToken
      );

      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        videoCaptureDefaults: { resolution: VideoPresets.h720.resolution },
        audioCaptureDefaults: {
          echoCancellation: true,      // INV-M05: Hardware AEC
          noiseSuppression: true,      // INV-M05: Noise suppression
          autoGainControl: true,       // INV-M05: Auto gain control
          sampleRate: 48000,           // INV-M06: Opus-native rate
          channelCount: 1,             // Mono voice
        },
      });

      roomRef.current = room;
      wireRoom(room);

      await room.connect(livekitUrl, token);

      try {
        await room.startAudio();
      } catch (_) {}

      try {
        await room.localParticipant.setMicrophoneEnabled(!isAudioMuted);
      } catch (err) {
        console.warn('Microphone permission notice:', err);
        setIsAudioMuted(true);
      }

      try {
        await room.localParticipant.setCameraEnabled(!isVideoMuted);
        setTimeout(attachLocalCamera, 300);
      } catch (err) {
        console.warn('Camera permission notice:', err);
        setIsVideoMuted(true);
      }

      const initialMap = new Map<string, RemoteParticipant>();
      room.remoteParticipants.forEach((p, id) => {
        initialMap.set(id, p);
        if (id === EVA_IDENTITY) setEvaState('connected');
      });
      setParticipants(initialMap);

      setActiveRoomName(resolvedRoom);
      setActiveParticipant(resolvedIdentity);
      setElapsedSeconds(0);
      setInLobby(false);
    } catch (err: any) {
      console.error('Failed to enter meeting room:', err);
      setJoinError(err.message || 'Could not join meeting room.');
    } finally {
      setIsConnecting(false);
    }
  };

  const toggleAudio = async () => {
    if (!roomRef.current) return;
    const target = !isAudioMuted;
    try {
      await roomRef.current.localParticipant.setMicrophoneEnabled(!target);
      setIsAudioMuted(target);
      userManuallyMuted.current = target;
    } catch (err) {
      console.error('Error toggling microphone', err);
    }
  };

  const toggleVideo = async () => {
    if (!roomRef.current) return;
    const target = !isVideoMuted;
    try {
      await roomRef.current.localParticipant.setCameraEnabled(!target);
      setIsVideoMuted(target);
      if (!target) {
        setTimeout(attachLocalCamera, 200);
      }
    } catch (err) {
      console.error('Error toggling camera', err);
    }
  };

  const handleEndCall = () => {
    if (roomRef.current) {
      roomRef.current.disconnect();
      roomRef.current = null;
    }
    setInLobby(true);
    setElapsedSeconds(0);
    if (onLeave) onLeave();
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = chatMessage.trim();
    if (!roomRef.current || !text) return;

    try {
      await roomRef.current.localParticipant.publishData(new TextEncoder().encode('link'), {
        reliable: true,
        topic: EVA_TARGET_TOPIC,
      });
    } catch (_) {}

    try {
      await roomRef.current.localParticipant.sendText(text, { topic: 'lk.chat' });
    } catch (_) {}

    const time = new Date().toTimeString().slice(3, 8);
    setTranscripts((prev) => [
      ...prev,
      {
        id: `chat-${Date.now()}-${Math.random()}`,
        speaker: activeParticipant,
        text,
        isEva: false,
        time,
      },
    ]);
    setChatMessage('');
  };

  const handlePromptEva = () => {
    setIsDrawerOpen(true);
    setTimeout(() => {
      if (chatInputRef.current) {
        chatInputRef.current.focus();
        if (!chatInputRef.current.value) {
          setChatMessage('Eva, ');
        }
      }
    }, 150);
  };

  const handleCreateInvite = async () => {
    setIsGeneratingInvite(true);
    setCopiedInvite(false);
    try {
      const res = await fetch(`${DEFAULT_BACKEND}/api/meet/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_name: activeRoomName,
          identity: inviteClientName.trim() || 'Client',
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setInviteUrl(data.join_url || `${DEFAULT_BACKEND}/meet?room=${activeRoomName}`);
      } else {
        setInviteUrl(`${DEFAULT_BACKEND}/meet?room=${activeRoomName}`);
      }
    } catch (_) {
      setInviteUrl(`${DEFAULT_BACKEND}/meet?room=${activeRoomName}`);
    } finally {
      setIsGeneratingInvite(false);
    }
  };

  const handleCopyInviteUrl = () => {
    if (!inviteUrl) return;
    navigator.clipboard.writeText(inviteUrl);
    setCopiedInvite(true);
    setTimeout(() => setCopiedInvite(false), 2000);
  };

  useEffect(() => {
    return () => {
      if (roomRef.current) {
        roomRef.current.disconnect();
      }
    };
  }, []);

  // --------------------------------------------------------------------------
  // LOBBY VIEW (Android Optimized with Dynamic Insets)
  // --------------------------------------------------------------------------
  if (inLobby) {
    return (
      <div className="min-h-screen w-full bg-white flex flex-col justify-center items-center p-4 pt-[max(1.25rem,env(safe-area-inset-top))] pb-[max(2rem,env(safe-area-inset-bottom))] font-['Inter']">
        <div className="bg-white w-full max-w-sm border-2 border-black p-5 space-y-4 shadow-[4px_4px_0px_#000]">
          {/* Header */}
          <div className="flex items-center gap-3 pb-3 border-b border-black">
            <svg className="w-7 h-7 shrink-0" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="6" cy="20" r="2.5" fill="#000000" />
              <circle cx="15" cy="11" r="2.5" fill="#000000" />
              <circle cx="15" cy="20" r="2.5" fill="#000000" />
              <circle cx="15" cy="29" r="2.5" fill="#000000" />
              <circle cx="25" cy="14" r="2.5" fill="#000000" />
              <circle cx="25" cy="26" r="2.5" fill="#000000" />
              <circle cx="34" cy="20" r="3.5" fill="#E6391E" />
              <line x1="6" y1="20" x2="15" y2="11" stroke="#000000" strokeWidth="1.2" />
              <line x1="6" y1="20" x2="15" y2="20" stroke="#000000" strokeWidth="1.2" />
              <line x1="6" y1="20" x2="15" y2="29" stroke="#000000" strokeWidth="1.2" />
              <line x1="15" y1="11" x2="25" y2="14" stroke="#000000" strokeWidth="1.2" />
              <line x1="15" y1="20" x2="25" y2="14" stroke="#000000" strokeWidth="1.2" />
              <line x1="15" y1="20" x2="25" y2="26" stroke="#000000" strokeWidth="1.2" />
              <line x1="15" y1="29" x2="25" y2="26" stroke="#000000" strokeWidth="1.2" />
              <line x1="25" y1="14" x2="34" y2="20" stroke="#E6391E" strokeWidth="1.5" />
              <line x1="25" y1="26" x2="34" y2="20" stroke="#E6391E" strokeWidth="1.5" />
            </svg>
            <div>
              <span className="font-['Space_Grotesk'] font-bold text-lg tracking-tight text-black">AlphaBrain</span>
              <p className="text-[10px] font-mono text-neutral-500">LiveKit WebRTC · Eva Voice Enclave</p>
            </div>
          </div>

          {/* Two-Tab Navigation: Create vs Join */}
          <div className="grid grid-cols-2 gap-1 border border-black p-1 bg-neutral-100 text-xs font-mono font-bold uppercase">
            <button
              type="button"
              onClick={() => setLobbyTab('create')}
              className={`py-1.5 transition-colors ${
                lobbyTab === 'create' ? 'bg-black text-white' : 'text-neutral-600 hover:text-black'
              }`}
            >
              Create
            </button>
            <button
              type="button"
              onClick={() => setLobbyTab('join')}
              className={`py-1.5 transition-colors ${
                lobbyTab === 'join' ? 'bg-black text-white' : 'text-neutral-600 hover:text-black'
              }`}
            >
              Join / Link
            </button>
          </div>

          {lobbyTab === 'create' ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleJoinMeeting(roomNameInput.trim() || DEFAULT_ROOM);
              }}
              className="space-y-3"
            >
              <div>
                <label className="block text-xs font-semibold text-neutral-700">Your Name</label>
                <input
                  type="text"
                  required
                  maxLength={128}
                  value={participantName}
                  onChange={(e) => setParticipantName(e.target.value)}
                  className="mt-1 w-full border border-black px-3 py-1.5 text-xs text-black focus:outline-none focus:ring-1 focus:ring-black"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700">Room Code</label>
                <div className="flex gap-2 mt-1">
                  <input
                    type="text"
                    required
                    pattern="[A-Za-z0-9][A-Za-z0-9._\-]{0,127}"
                    value={roomNameInput}
                    onChange={(e) => setRoomNameInput(e.target.value)}
                    className="flex-1 border border-black px-3 py-1.5 text-xs text-black font-mono focus:outline-none focus:ring-1 focus:ring-black"
                  />
                  <button
                    type="button"
                    onClick={() => setRoomNameInput(`meet-${Math.random().toString(36).substring(2, 6)}`)}
                    className="border border-black px-2.5 py-1 text-[11px] font-mono font-bold hover:bg-neutral-100"
                  >
                    RND
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700">Language</label>
                <select
                  value={selectedLanguage}
                  onChange={(e) => setSelectedLanguage(e.target.value)}
                  className="mt-1 w-full border border-black px-3 py-1.5 text-xs bg-white text-black"
                >
                  <option value="hi">Hindi (हिन्दी)</option>
                  <option value="en">English</option>
                  <option value="zh">Chinese (中文)</option>
                  <option value="ja">Japanese (日本語)</option>
                  <option value="ko">Korean (한국어)</option>
                  <option value="es">Spanish (Español)</option>
                  <option value="fr">French (Français)</option>
                  <option value="de">German (Deutsch)</option>
                </select>
              </div>

              <label className="flex items-center gap-2 text-xs font-semibold text-neutral-700 pt-1">
                <input
                  type="checkbox"
                  checked={translateEnabled}
                  onChange={(e) => setTranslateEnabled(e.target.checked)}
                  className="accent-black w-4 h-4 rounded-none border-black"
                />
                Live Translation (Gemini Audio)
              </label>

              {joinError && (
                <p className="text-xs text-[#E6391E] border border-[#E6391E] p-2" role="alert">
                  {joinError}
                </p>
              )}

              <button
                type="submit"
                disabled={isConnecting}
                className="w-full py-2.5 bg-black text-white font-semibold text-xs tracking-wider uppercase hover:bg-neutral-800 transition-all disabled:opacity-50"
              >
                {isConnecting ? 'CONNECTING…' : 'JOIN ROOM'}
              </button>
            </form>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const parsed = parseMeetingInput(joinLinkInput);
                handleJoinMeeting(parsed.roomName || DEFAULT_ROOM, parsed.inviteToken);
              }}
              className="space-y-3"
            >
              <div>
                <label className="block text-xs font-semibold text-neutral-700">Paste Link or Room Code</label>
                <input
                  type="text"
                  required
                  placeholder="https://.../meet#invite=... or room code"
                  value={joinLinkInput}
                  onChange={(e) => setJoinLinkInput(e.target.value)}
                  className="mt-1 w-full border border-black px-3 py-1.5 text-xs text-black font-mono focus:outline-none focus:ring-1 focus:ring-black"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700">Your Name</label>
                <input
                  type="text"
                  required
                  maxLength={128}
                  value={participantName}
                  onChange={(e) => setParticipantName(e.target.value)}
                  className="mt-1 w-full border border-black px-3 py-1.5 text-xs text-black focus:outline-none focus:ring-1 focus:ring-black"
                />
              </div>

              {joinError && (
                <p className="text-xs text-[#E6391E] border border-[#E6391E] p-2" role="alert">
                  {joinError}
                </p>
              )}

              <button
                type="submit"
                disabled={isConnecting || !joinLinkInput.trim()}
                className="w-full py-2.5 bg-black text-white font-semibold text-xs tracking-wider uppercase hover:bg-neutral-800 transition-all disabled:opacity-50"
              >
                {isConnecting ? 'CONNECTING…' : 'JOIN ROOM'}
              </button>
            </form>
          )}

          <div className="pt-2 border-t border-neutral-200 flex items-center justify-between text-[10px] font-mono text-neutral-400">
            <span>Direct WebRTC Engine</span>
            <span className="text-emerald-600 font-bold">NO TOKEN NEEDED</span>
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // ACTIVE WEBRTC MEETING VIEW (Android Margin & Layout Optimized)
  // --------------------------------------------------------------------------
  const humanRemotes = Array.from(participants.values()).filter((p) => p.identity !== EVA_IDENTITY);

  return (
    <div
      className={`h-screen w-screen flex flex-col justify-between overflow-hidden font-['Inter'] pt-[max(0.5rem,env(safe-area-inset-top))] pb-[max(1.75rem,env(safe-area-inset-bottom))] ${
        isDarkMode ? 'dark bg-neutral-950 text-white' : 'bg-white text-black'
      }`}
    >
      {/* Mobile Header Bar */}
      <header className="h-14 border-b border-black flex items-center justify-between px-4 shrink-0 bg-white z-30">
        <div className="flex items-center gap-2">
          <svg className="w-6 h-6 shrink-0" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="6" cy="20" r="2.5" fill="#000000" />
            <circle cx="15" cy="11" r="2.5" fill="#000000" />
            <circle cx="15" cy="20" r="2.5" fill="#000000" />
            <circle cx="15" cy="29" r="2.5" fill="#000000" />
            <circle cx="25" cy="14" r="2.5" fill="#000000" />
            <circle cx="25" cy="26" r="2.5" fill="#000000" />
            <circle cx="34" cy="20" r="3.5" fill="#E6391E" />
            <line x1="6" y1="20" x2="15" y2="11" stroke="#000000" strokeWidth="1.2" />
            <line x1="6" y1="20" x2="15" y2="20" stroke="#000000" strokeWidth="1.2" />
            <line x1="6" y1="20" x2="15" y2="29" stroke="#000000" strokeWidth="1.2" />
            <line x1="15" y1="11" x2="25" y2="14" stroke="#000000" strokeWidth="1.2" />
            <line x1="15" y1="20" x2="25" y2="14" stroke="#000000" strokeWidth="1.2" />
            <line x1="15" y1="20" x2="25" y2="26" stroke="#000000" strokeWidth="1.2" />
            <line x1="15" y1="29" x2="25" y2="26" stroke="#000000" strokeWidth="1.2" />
            <line x1="25" y1="14" x2="34" y2="20" stroke="#E6391E" strokeWidth="1.5" />
            <line x1="25" y1="26" x2="34" y2="20" stroke="#E6391E" strokeWidth="1.5" />
          </svg>
          <span className="font-['Space_Grotesk'] text-lg font-bold tracking-tight text-black">AlphaBrain</span>
          <span className="font-mono text-[10px] text-neutral-400 truncate max-w-[90px]">/{activeRoomName}</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-black font-mono text-xs font-semibold">
            <span className="material-symbols-outlined text-[16px]">group</span>
            <span>{participants.size + 1}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              setShowInviteModal(true);
              handleCreateInvite();
            }}
            className="flex items-center gap-1 px-2.5 py-1 border border-black text-black hover:bg-neutral-50 font-mono text-[11px] uppercase font-bold"
          >
            <span className="material-symbols-outlined text-[14px]">upload</span>
            <span>SHARE</span>
          </button>
        </div>
      </header>

      {/* Main Video Stage Area */}
      <main className="flex-1 p-2 overflow-hidden flex flex-col relative">
        <div className="stage-grid layout-2 flex-1 min-h-0">
          {/* Tile 1: Founder (Local) */}
          <div className="video-tile-container relative flex items-center justify-center bg-black border border-black min-h-0">
            <video
              ref={localVideoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover ${isVideoMuted ? 'hidden' : 'block'}`}
            />
            {isVideoMuted && (
              <div className="flex flex-col items-center gap-1 text-neutral-500 font-mono text-xs">
                <span className="material-symbols-outlined text-[28px]">videocam_off</span>
                <span>CAMERA OFF</span>
              </div>
            )}
            <div className="speaker-badge">
              <span className="w-2 h-2 rounded-full bg-[#E6391E]"></span>
              <span className="truncate max-w-[120px]">{activeParticipant}</span>
            </div>
          </div>

          {/* Tile 2: Eva AI Architect */}
          <div className="video-tile-container relative bg-neutral-950 flex flex-col items-center justify-center border border-black min-h-0">
            {evaState === 'speaking' && (
              <div className="absolute top-2 right-2 z-10">
                <div className="active-wave">
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
            <div className="flex flex-col items-center gap-2 text-neutral-400">
              <div
                className={`w-12 h-12 rounded-full border flex items-center justify-center shadow-md transition-all ${
                  evaState === 'speaking'
                    ? 'border-[#E6391E] shadow-[0_0_15px_#E6391E] scale-105'
                    : 'border-neutral-700 bg-neutral-900'
                }`}
              >
                <span className="material-symbols-outlined text-[22px] text-[#E6391E]">graphic_eq</span>
              </div>
              <div className="font-['Fira_Code'] text-[9px] uppercase tracking-widest text-neutral-400">
                Gemini Live Voice Active
              </div>
            </div>
            <div className="speaker-badge">
              <span className="w-2 h-2 rounded-full bg-[#E6391E]"></span>
              <span>Eva (AI Architect)</span>
            </div>
          </div>

          {/* Remote Client Tile */}
          {humanRemotes.length > 0 && (
            <div className="video-tile-container relative bg-neutral-900 flex items-center justify-center border border-black min-h-0">
              <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-cover" />
              <div className="speaker-badge">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                <span>{humanRemotes[0].name || humanRemotes[0].identity}</span>
              </div>
            </div>
          )}
        </div>

        {/* Mobile Slide-Up Live Notes Drawer */}
        {isDrawerOpen && (
          <aside className="absolute inset-x-2 bottom-2 top-2 z-40 bg-white border-2 border-black flex flex-col shadow-2xl">
            <div className="p-3 border-b border-black flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="font-['Fira_Code'] text-xs uppercase font-bold tracking-wider text-black">LIVE NOTES</h2>
                <span className="font-mono text-[9px] text-neutral-400">PCM 24kHz</span>
              </div>
              <button
                type="button"
                onClick={() => setIsDrawerOpen(false)}
                className="font-mono font-bold text-sm px-2 py-0.5 border border-black hover:bg-neutral-100"
              >
                ✕
              </button>
            </div>

            <div ref={transcriptScrollRef} className="flex-1 overflow-y-auto divide-y divide-black/10 text-xs p-2">
              {transcripts.length === 0 ? (
                <div className="p-4 text-center font-mono text-neutral-400 text-xs">
                  Speech will transcribe here live...
                </div>
              ) : (
                transcripts.map((item) => (
                  <div key={item.id} className="py-2 px-1 flex gap-2">
                    <span className="font-mono text-neutral-400 text-[10px] shrink-0">{item.time}</span>
                    <div className="space-y-0.5 flex-1">
                      <div className={`font-mono font-bold text-xs ${item.isEva ? 'text-[#E6391E]' : 'text-black'}`}>
                        {item.speaker}
                      </div>
                      <p className="font-mono text-neutral-800 leading-relaxed text-xs">{item.text}</p>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="p-2 border-t border-black bg-neutral-50">
              <form onSubmit={handleSendChat} className="flex gap-2">
                <input
                  ref={chatInputRef}
                  type="text"
                  placeholder="Ask Eva..."
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  className="flex-1 border border-black px-2.5 py-1.5 text-xs text-black font-mono focus:outline-none focus:ring-1 focus:ring-black bg-white"
                />
                <button
                  type="submit"
                  className="border border-black px-3 py-1.5 text-xs font-mono font-bold bg-black text-white hover:bg-neutral-800"
                >
                  SEND
                </button>
              </form>
            </div>
          </aside>
        )}
      </main>

      {/* Bottom Bar Control Strip (Protected Above Android 3-Button Navbar) */}
      <footer className="h-16 border-t border-black bg-white flex items-center justify-between px-4 shrink-0 z-30">
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Mic */}
          <button
            type="button"
            onClick={toggleAudio}
            className={`w-9 h-9 rounded-full border border-black flex items-center justify-center transition-all ${
              isAudioMuted ? 'bg-rose-500 text-white' : 'bg-black text-white'
            }`}
            title="Mute / Unmute Mic"
          >
            <span className="material-symbols-outlined text-[18px]">{isAudioMuted ? 'mic_off' : 'mic'}</span>
          </button>

          {/* Cam */}
          <button
            type="button"
            onClick={toggleVideo}
            className={`w-9 h-9 rounded-full border border-black flex items-center justify-center transition-all ${
              isVideoMuted ? 'bg-rose-500 text-white' : 'bg-black text-white'
            }`}
            title="Toggle Video"
          >
            <span className="material-symbols-outlined text-[18px]">{isVideoMuted ? 'videocam_off' : 'videocam'}</span>
          </button>

          {/* Transcript Drawer */}
          <button
            type="button"
            onClick={() => setIsDrawerOpen(!isDrawerOpen)}
            className={`w-9 h-9 rounded-full border border-black flex items-center justify-center transition-all ${
              isDrawerOpen ? 'bg-[#E6391E] text-white' : 'bg-black text-white'
            }`}
            title="Toggle Notes / Captions"
          >
            <span className="material-symbols-outlined text-[18px]">closed_caption</span>
          </button>

          {/* Prompt Eva */}
          <button
            type="button"
            onClick={handlePromptEva}
            className="w-9 h-9 rounded-full bg-black text-white border border-black flex items-center justify-center"
            title="Prompt Eva"
          >
            <span className="material-symbols-outlined text-[18px]">front_hand</span>
          </button>

          {/* End Call Red Button */}
          <button
            type="button"
            onClick={handleEndCall}
            className="h-9 px-3 rounded bg-[#E6391E] text-white flex items-center justify-center gap-1 font-mono text-xs font-bold"
            title="End Call"
          >
            <span className="material-symbols-outlined text-[18px]">call_end</span>
          </button>
        </div>

        {/* Digital Timer */}
        <div className="font-mono text-xs font-bold text-black pl-2">
          {formatTimer(elapsedSeconds)}
        </div>
      </footer>

      {/* Share / Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-[110] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border-2 border-black p-5 w-full max-w-sm shadow-2xl space-y-3">
            <div className="flex items-center justify-between border-b border-black pb-2">
              <span className="font-['Space_Grotesk'] font-bold text-sm text-black">Invite Client</span>
              <button
                type="button"
                onClick={() => setShowInviteModal(false)}
                className="font-mono font-bold text-sm hover:text-[#E6391E]"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-700">Client Name</label>
              <div className="flex gap-2 mt-1">
                <input
                  type="text"
                  value={inviteClientName}
                  onChange={(e) => setInviteClientName(e.target.value)}
                  className="flex-1 border border-black px-2.5 py-1 text-xs text-black font-mono focus:outline-none focus:ring-1 focus:ring-black"
                />
                <button
                  type="button"
                  onClick={handleCreateInvite}
                  disabled={isGeneratingInvite}
                  className="border border-black px-2.5 py-1 text-xs font-mono font-bold bg-black text-white hover:bg-neutral-800"
                >
                  {isGeneratingInvite ? 'GEN…' : 'UPDATE'}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-700">Client Web Link</label>
              <div className="flex gap-2 mt-1">
                <input
                  type="text"
                  readOnly
                  value={inviteUrl || 'Generating link...'}
                  className="flex-1 border border-black px-2.5 py-1 text-xs text-neutral-700 bg-neutral-50 font-mono truncate"
                />
                <button
                  type="button"
                  onClick={handleCopyInviteUrl}
                  disabled={!inviteUrl}
                  className="border border-black px-2.5 py-1 text-xs font-mono font-bold bg-black text-white hover:bg-neutral-800"
                >
                  {copiedInvite ? 'COPIED' : 'COPY'}
                </button>
              </div>
              <p className="text-[10px] text-neutral-500 mt-1 font-mono">
                Open in any browser to join with Eva voice enclave.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
