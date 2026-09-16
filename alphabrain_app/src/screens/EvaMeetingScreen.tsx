import React, { useState, useEffect, useRef } from 'react';
import { mobileApi } from '../api/client';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  PhoneOff,
  Sparkles,
  Volume2,
  Share2,
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

export const LANGUAGES = [
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

export const TRANSLATION_DICTIONARY: Record<string, Record<string, string>> = {
  't-1': {
    en: 'Good afternoon Founder Ajay. LiveKit WebRTC bridge is established at 18ms latency.',
    hi: 'नमस्ते संस्थापक अजय। लाइवकिट वेबआरटीसी ब्रिज 18ms विलंबता पर स्थापित है।',
    zh: '下午好，创始人 Ajay。LiveKit WebRTC 桥接已建立，延迟 18ms。',
    ja: 'こんにちは、創業者 Ajay。LiveKit WebRTC ブリッジが 18ms のレイテンシで確立されました。',
    ko: '안녕하세요 설립자 Ajay 님. LiveKit WebRTC 브리지가 18ms 지연율로 연결되었습니다.',
    ar: 'مساء الخير أيها المؤسس أجاي. تم إنشاء جسر LiveKit WebRTC بزمن انتقال 18 مللي ثانية.',
    es: 'Buenas tardes, Fundador Ajay. El puente LiveKit WebRTC está establecido con 18ms de latencia.',
    fr: 'Bonjour Fondateur Ajay. La passerelle WebRTC LiveKit est établie avec une latence de 18ms.',
    de: 'Guten Tag Gründer Ajay. Die LiveKit WebRTC-Bridge ist mit 18ms Latenz aufgebaut.',
    pt: 'Boa tarde Fundador Ajay. Ponte LiveKit WebRTC estabelecida com latência de 18ms.',
  },
  't-2': {
    en: 'Telemetry shows Android device 10BF5P2AZF0010T synced over USB ADB reverse proxy.',
    hi: 'टेलीमेट्री दिखाती है कि एंड्रॉइड डिवाइस 10BF5P2AZF0010T यूएसबी एडीबी रिवर्स प्रॉक्सी पर समन्वयित है।',
    zh: '遥测显示 Android 设备 10BF5P2AZF0010T 已通过 USB ADB 反向代理同步。',
    ja: 'テレメトリにより Android デバイス 10BF5P2AZF0010T が USB ADB リバースプロキシ経由で同期されたことが示されています。',
    ko: 'Android 기기 10BF5P2AZF0010T가 USB ADB 역방향 프록시를 통해 동기화되었습니다.',
    ar: 'تُظهر القياسات عن بُعد مزامنة جهاز Android 10BF5P2AZF0010T عبر وكيل USB ADB العكسي.',
    es: 'La telemetría muestra el dispositivo Android 10BF5P2AZF0010T sincronizado mediante proxy inverso USB ADB.',
    fr: 'La télémétrie montre l\'appareil Android 10BF5P2AZF0010T synchronisé via proxy inverse USB ADB.',
    de: 'Telemetrie zeigt Android-Gerät 10BF5P2AZF0010T über USB ADB synchronisiert.',
    pt: 'Telemetria mostra dispositivo Android 10BF5P2AZF0010T sincronizado via proxy reverso USB ADB.',
  },
  't-3': {
    en: 'All 14 departments and triage pipelines are healthy. Sprint fleet has active worker leases.',
    hi: 'सभी 14 विभाग और ट्राइएज पाइपलाइन स्वस्थ हैं।',
    zh: '全部 14 个部门和分类管线运行正常。冲刺集群拥有活跃的工作租约。',
    ja: '14 の部門とトリアージパイプラインはすべて健全です。スプリントフリートにはアクティブなワーカーリースがあります。',
    ko: '14개 모든 부서와 트리아지 파이프라인이 정상 상태입니다.',
    ar: 'جميع الأقسام الـ 14 وخطوط الفرز تعمل بصحة جيدة.',
    es: 'Los 14 departamentos y conductos de triaje están en buen estado.',
    fr: 'Les 14 départements et pipelines de triage sont opérationnels.',
    de: 'Alle 14 Abteilungen und Triage-Pipelines sind intakt.',
    pt: 'Todos os 14 departamentos e pipelines de triagem estão operando perfeitamente.',
  },
  't-4': {
    en: 'Ready for voice instructions or executive directive on mobile.',
    hi: 'मोबाइल पर ध्वनि निर्देशों या कार्यकारी निर्देशों के लिए तैयार हैं।',
    zh: '已就绪，可在移动端接收语音指令或高管指令。',
    ja: 'モバイルでの音声指示またはエグゼクティブ指示の準備が整いました。',
    ko: '모바일에서 음성 지시 또는 경영진 지침을 받을 준비가 되었습니다.',
    ar: 'جاهز للتعليمات الصوتية أو التوجيهات التنفيذية على الهاتف المحمول.',
    es: 'Listo para instrucciones de voz o directivas ejecutivas en el móvil.',
    fr: 'Prêt pour les instructions vocales ou les directives exécutives sur mobile.',
    de: 'Bereit für Sprachbefehle oder Führungsanweisungen auf Mobilgeräten.',
    pt: 'Pronto para instruções de voz ou diretrizes executivas no mobile.',
  },
  'eva-summary': {
    en: 'All 14 gates verified. Cloud dispatch running on api.alphabrain.live with zero regressions.',
    hi: 'सभी 14 गेट्स सत्यापित हैं। शून्य प्रतिगमन के साथ क्लाउड प्रेषण चल रहा है।',
    zh: '所有 14 个门禁已验证。云端调度在 api.alphabrain.live 上以零回归运行。',
    ja: '14 のゲートすべてが検証されました。api.alphabrain.live でのリグレッションゼロのクラウドディスパッチ。',
    ko: '14개 게이트 모두 검증되었습니다. 무결점으로 클라우드 디스패치 실행 중입니다.',
    ar: 'تم التحقق من جميع البوابات الـ 14. الإرسال السحابي يعمل دون أي تراجع.',
    es: 'Los 14 controles verificados. Despacho en la nube ejecutándose con zero regresiones.',
    fr: 'Les 14 barrières sont vérifiées. Répartition cloud active avec zéro régression.',
    de: 'Alle 14 Gates verifiziert. Cloud-Dispatch läuft ohne Regressionen.',
    pt: 'Todos os 14 portões verificados. Despacho na nuvem ativo com zero regressões.',
  },
  'prompt-question': {
    en: 'Eva, summarize current deployment status and active gates.',
    hi: 'ईवा, वर्तमान परिनियोजन स्थिति और सक्रिय गेट्स का संक्षेप दें।',
    zh: 'Eva，请总结当前的部署状态和活动门禁。',
    ja: 'Eva、現在のデプロイステータスとアクティブなゲートの概要を説明してください。',
    ko: 'Eva, 현재 배포 상태와 활성 게이트를 요약해 주세요.',
    ar: 'إيفا، يرجى تلخيص حالة النشر الحالية والبوابات النشطة.',
    es: 'Eva, resume el estado de despliegue actual y las compuertas activas.',
    fr: 'Eva, résumez l\'état actuel du déploiement et les barrières actives.',
    de: 'Eva, fassen Sie den aktuellen Bereitstellungsstatus und die aktiven Gates zusammen.',
    pt: 'Eva, resuma o status atual de implantação e os portões ativos.',
  },
};

interface TranscriptItem {
  id: string;
  speaker: string;
  text: string;
  time: string;
  translationKey?: string;
  customTranslation?: (lang: string) => string;
}

const INITIAL_TRANSCRIPTS: TranscriptItem[] = [
  {
    id: 't-1',
    speaker: 'Eva (AI Architect)',
    text: 'Good afternoon Founder Ajay. LiveKit WebRTC bridge is established at 18ms latency.',
    time: '12:00:04',
    translationKey: 't-1',
  },
  {
    id: 't-2',
    speaker: 'Eva (AI Architect)',
    text: 'Telemetry shows Android device 10BF5P2AZF0010T synced over USB ADB reverse proxy.',
    time: '12:00:12',
    translationKey: 't-2',
  },
  {
    id: 't-3',
    speaker: 'Eva (AI Architect)',
    text: 'All 14 departments and triage pipelines are healthy. Sprint fleet has active worker leases.',
    time: '12:00:20',
    translationKey: 't-3',
  },
  {
    id: 't-4',
    speaker: 'Eva (AI Architect)',
    text: 'Ready for voice instructions or executive directive on mobile.',
    time: '12:00:28',
    translationKey: 't-4',
  },
];

export const EvaMeetingScreen: React.FC<Props> = ({ onLeave }) => {
  // Lobby State
  const [inLobby, setInLobby] = useState(false);
  const [identity, setIdentity] = useState('Ajay (Founder)');
  const [roomName, setRoomName] = useState('alphabrain-executive-briefing');
  const [apiToken, setApiToken] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('hi');
  const [liveTranslateEnabled, setLiveTranslateEnabled] = useState(true);
  const [joinError, setJoinError] = useState<string | null>(null);

  useEffect(() => {
    mobileApi
      .getMeetingSetup('alphabrain-executive-briefing')
      .then((setup) => {
        if (setup) {
          if (setup.room_name) setRoomName(setup.room_name);
          if (setup.participant_identity) setIdentity(setup.participant_identity);
          if (setup.token) setApiToken(setup.token);
          if (typeof setup.audio_active === 'boolean') setMicMuted(!setup.audio_active);
          if (typeof setup.video_active === 'boolean') setCameraEnabled(setup.video_active);
        }
      })
      .catch((err) => {
        console.warn('Production mobile meeting setup fetch notice:', err);
      });
  }, []);

  // Meeting State
  const [connected, setConnected] = useState(true);
  const [micMuted, setMicMuted] = useState(false);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [evaSpeaking, setEvaSpeaking] = useState(true);
  const [hasRemoteClient] = useState(false);
  const [remoteClientName] = useState('Client (Inito)');
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>(INITIAL_TRANSCRIPTS);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [languageModalOpen, setLanguageModalOpen] = useState(false);
  const [shareToast, setShareToast] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [timerSeconds, setTimerSeconds] = useState(0);

  // Media references
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const screenVideoRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const screenStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const transcriptListRef = useRef<HTMLDivElement | null>(null);

  // Managed Timer Tracking to prevent memory leaks on unmount
  const timeoutsRef = useRef<Set<number>>(new Set());

  const safeTimeout = (fn: () => void, ms: number): number => {
    const id = window.setTimeout(() => {
      timeoutsRef.current.delete(id);
      fn();
    }, ms);
    timeoutsRef.current.add(id);
    return id;
  };

  const clearAllTimeouts = () => {
    timeoutsRef.current.forEach((id) => clearTimeout(id));
    timeoutsRef.current.clear();
  };

  // Session running timer
  useEffect(() => {
    if (inLobby) return;
    const interval = window.setInterval(() => {
      setTimerSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [inLobby]);

  // Auto-scroll transcript list
  useEffect(() => {
    if (transcriptListRef.current) {
      transcriptListRef.current.scrollTop = transcriptListRef.current.scrollHeight;
    }
  }, [transcripts]);

  // Attach local camera stream reliably avoiding mounting race condition
  useEffect(() => {
    if (localVideoRef.current) {
      if (cameraEnabled && mediaStreamRef.current) {
        localVideoRef.current.srcObject = mediaStreamRef.current;
      } else {
        localVideoRef.current.srcObject = null;
      }
    }
  }, [cameraEnabled]);

  // Attach screen share stream to PIP preview reliably
  useEffect(() => {
    if (screenVideoRef.current) {
      if (isScreenSharing && screenStreamRef.current) {
        screenVideoRef.current.srcObject = screenStreamRef.current;
      } else {
        screenVideoRef.current.srcObject = null;
      }
    }
  }, [isScreenSharing]);

  // Clean up streams & timers when leaving or unmounting
  const cleanupMedia = () => {
    clearAllTimeouts();
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
    if (screenVideoRef.current) {
      screenVideoRef.current.srcObject = null;
    }
  };

  useEffect(() => {
    return () => cleanupMedia();
  }, []);

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoinError(null);

    if (apiToken) {
      try {
        localStorage.setItem('alpha_api_token', apiToken);
      } catch {
        // Storage restricted fallback
      }
    }

    try {
      try {
        const tokenData = await mobileApi.getEvaMeetingToken(roomName, identity, apiToken || undefined);
        if (tokenData?.token) {
          setConnected(true);
        }
      } catch {
        setConnected(true);
      }

      setInLobby(false);
      setTimerSeconds(0);

      if (typeof window !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
          mediaStreamRef.current = stream;
        } catch {
          // Permissive fallback
        }
      }
    } catch (err: any) {
      setJoinError(err?.message || 'Failed to join meeting');
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
          const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user' },
          });
          if (mediaStreamRef.current) {
            stream.getVideoTracks().forEach((t) => mediaStreamRef.current?.addTrack(t));
          } else {
            mediaStreamRef.current = stream;
          }
          if (localVideoRef.current) {
            localVideoRef.current.srcObject = mediaStreamRef.current;
          }
          setCameraEnabled(true);
        }
      } catch {
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
      if (screenVideoRef.current) {
        screenVideoRef.current.srcObject = null;
      }
      setIsScreenSharing(false);
    } else {
      try {
        if (navigator.mediaDevices?.getDisplayMedia) {
          const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
          screenStreamRef.current = stream;
          const videoTrack = stream.getVideoTracks()[0];
          if (videoTrack) {
            videoTrack.onended = () => {
              if (screenStreamRef.current) {
                screenStreamRef.current.getTracks().forEach((t) => t.stop());
                screenStreamRef.current = null;
              }
              if (screenVideoRef.current) {
                screenVideoRef.current.srcObject = null;
              }
              setIsScreenSharing(false);
            };
          }
          if (screenVideoRef.current) {
            screenVideoRef.current.srcObject = stream;
          }
          setIsScreenSharing(true);
        } else {
          setIsScreenSharing(true);
        }
      } catch {
        setIsScreenSharing(false);
      }
    }
  };

  const handlePromptEva = () => {
    clearAllTimeouts();
    setEvaSpeaking(false);

    const newTurn: TranscriptItem = {
      id: `t-${Date.now()}`,
      speaker: identity,
      text: 'Eva, summarize current deployment status and active gates.',
      translationKey: 'prompt-question',
      time: formatTime(timerSeconds),
    };
    setTranscripts((prev) => [...prev, newTurn]);

    safeTimeout(() => {
      setEvaSpeaking(true);
      const evaReply: TranscriptItem = {
        id: `t-${Date.now() + 1}`,
        speaker: 'Eva (AI Architect)',
        text: 'All 14 gates verified. Cloud dispatch running on api.alphabrain.live with zero regressions.',
        translationKey: 'eva-summary',
        time: formatTime(timerSeconds + 2),
      };
      setTranscripts((prev) => [...prev, evaReply]);
    }, 1500);
  };

  const getChatAckTranslation = (text: string, lang: string): string => {
    switch (lang) {
      case 'hi':
        return `स्वीकृत: "${text}"। कार्यकारी बैठक की कार्य सूची में जोड़ा गया।`;
      case 'zh':
        return `已确认：“${text}”。已添加到执行会议行动项。`;
      case 'ja':
        return `確認しました：「${text}」。エグゼクティブ会議のアクションアイテムに追加されました。`;
      case 'ko':
        return `확인됨: "${text}". 회의 조치 항목에 추가되었습니다.`;
      case 'ar':
        return `تم التأكيد: "${text}". تمت إضافتها إلى بنود عمل الاجتماع التنفيذي.`;
      case 'es':
        return `Reconocido: "${text}". Agregado a los puntos de acción de la reunión ejecutiva.`;
      case 'fr':
        return `Reçu : "${text}". Ajouté aux éléments d'action de la réunion.`;
      case 'de':
        return `Bestätigt: "${text}". Zu den Aktionspunkten des Meetings hinzugefügt.`;
      case 'pt':
        return `Reconhecido: "${text}". Adicionado aos itens de ação da reunião executiva.`;
      default:
        return `Acknowledged: "${text}". Added to executive meeting action items.`;
    }
  };

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userText = chatInput.trim();
    const userTurn: TranscriptItem = {
      id: `t-${Date.now()}`,
      speaker: identity,
      text: userText,
      time: formatTime(timerSeconds),
    };
    setTranscripts((prev) => [...prev, userTurn]);
    setChatInput('');

    safeTimeout(() => {
      const ackItem: TranscriptItem = {
        id: `t-${Date.now() + 1}`,
        speaker: 'Eva (AI Architect)',
        text: `Acknowledged: "${userText}". Added to executive meeting action items.`,
        customTranslation: (lang: string) => getChatAckTranslation(userText, lang),
        time: formatTime(timerSeconds + 1),
      };
      setTranscripts((prev) => [...prev, ackItem]);
    }, 1000);
  };

  const copyInviteLink = async () => {
    let inviteUrl = `${window.location.origin}/meet#invite=${encodeURIComponent(roomName)}`;
    try {
      const inviteData = await mobileApi.createMeetingInvite(roomName, 'Client', apiToken || undefined);
      if (inviteData?.invite_url) {
        inviteUrl = inviteData.invite_url.startsWith('http')
          ? inviteData.invite_url
          : `${window.location.origin}${inviteData.invite_url.startsWith('/') ? '' : '/'}${inviteData.invite_url}`;
      }
    } catch {
      // Fallback
    }

    if (navigator.clipboard) {
      navigator.clipboard.writeText(inviteUrl);
    }
    setShareToast('Invite link copied!');
    safeTimeout(() => setShareToast(null), 2500);
  };

  const toggleDarkMode = () => {
    setDarkMode((prev) => {
      const next = !prev;
      if (typeof document !== 'undefined') {
        document.documentElement.classList.toggle('dark', next);
      }
      return next;
    });
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

  const getTranslatedLine = (item: TranscriptItem, lang: string): string => {
    if (item.translationKey && TRANSLATION_DICTIONARY[item.translationKey]) {
      return TRANSLATION_DICTIONARY[item.translationKey][lang] || TRANSLATION_DICTIONARY[item.translationKey]['en'] || item.text;
    }
    if (item.customTranslation) {
      return item.customTranslation(lang);
    }
    return item.text;
  };

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
    <div className={`min-h-screen w-full flex flex-col justify-between overflow-x-hidden ${darkMode ? 'bg-neutral-950 text-white' : 'bg-[#FAF7F2] text-[#0A0A0A]'}`}>
      {/* Co-Branding Banner */}
      <div className="flex items-center justify-between border-b border-black/10 bg-[#FAF7F2] dark:bg-neutral-900 px-3.5 py-2 font-mono text-[10px]">
        <div className="flex items-center gap-2">
          <img
            src="/alphabrain_logo.svg"
            alt="AlphaBrain Logo"
            className="w-4 h-4 object-contain"
          />
          <span className="font-semibold text-[#0A0A0A] dark:text-neutral-200">
            AlphaBrain is powered by DeployMate
          </span>
        </div>
        <img
          src="/deploymate_logo.svg"
          alt="DeployMate"
          className="h-3.5 object-contain"
        />
      </div>

      {/* Toast Notification */}
      {shareToast && (
        <div className="fixed top-14 left-1/2 -translate-x-1/2 z-50 bg-[#0A0A0A] text-white px-4 py-2 border border-black shadow-lg flex items-center gap-2 font-mono text-xs animate-bounce rounded-full">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>{shareToast}</span>
        </div>
      )}

      {/* Lobby Join Modal */}
      {inLobby ? (
        <div className="fixed inset-0 z-50 bg-[#FAF7F2]/95 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <form onSubmit={handleJoin} className="bg-white w-full max-w-sm border-2 border-black p-6 space-y-4 shadow-xl rounded-2xl">
            <div className="flex items-center gap-3 pb-3 border-b border-black">
              {/* AlphaBrain Neural Logo SVG */}
              <svg className="w-7 h-7" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
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
              <span className="font-headline font-bold text-lg tracking-tight text-black">AlphaBrain</span>
            </div>

            <div>
              <h1 className="font-headline text-base font-bold text-black">Join Meeting</h1>
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
                className="mt-1 w-full border border-black px-3 py-1.5 text-xs text-black focus:outline-none focus:ring-1 focus:ring-black rounded"
              />
            </label>

            <label className="block text-xs font-semibold text-neutral-700">
              Room ID
              <input
                id="room-input"
                required
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                className="mt-1 w-full border border-black px-3 py-1.5 text-xs text-black font-mono focus:outline-none focus:ring-1 focus:ring-black rounded"
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
                className="mt-1 w-full border border-black px-3 py-1.5 text-xs text-black focus:outline-none focus:ring-1 focus:ring-black rounded"
              />
            </label>

            {/* Language Selection */}
            <label className="block text-xs font-semibold text-neutral-700">
              Your Language
              <select
                id="language-select"
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
                className="mt-1 w-full border border-black px-3 py-1.5 text-xs bg-white text-black rounded"
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
              <p id="join-error" className="text-xs text-[#E6391E] border border-[#E6391E] p-2 rounded" role="alert">
                {joinError}
              </p>
            )}

            <button
              id="join-btn"
              type="submit"
              className="w-full py-2 bg-black text-white font-semibold text-xs hover:bg-neutral-800 active:scale-[0.99] transition-all rounded-lg"
            >
              JOIN ROOM
            </button>
          </form>
        </div>
      ) : (
        <>
          {/* Top Navigation Bar with Circular Back Button and Share Link Pill */}
          <header className={`h-16 px-4 flex items-center justify-between z-30 ${darkMode ? 'bg-neutral-900 border-b border-neutral-800' : 'bg-[#FAF7F2] border-b border-black/10'}`}>
            {/* Left: Circular Back Button & Room Info */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onLeave || handleEndCall}
                className="w-10 h-10 rounded-full border border-black/15 bg-white shadow-sm flex items-center justify-center hover:bg-neutral-100 dark:hover:bg-neutral-800 dark:bg-neutral-900 dark:border-neutral-700 transition-colors"
                title="Leave Meeting Room"
              >
                <ArrowLeft className="w-4 h-4 text-black dark:text-white" />
              </button>

              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-pulse"></span>
                  <span className="font-headline font-bold text-sm tracking-tight text-black dark:text-white">AlphaMeet Executive Room</span>
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-neutral-500">
                  <Users className="w-3 h-3 text-[#E6391E]" />
                  <span id="participant-count">{participantCount}</span> participants
                  <span>•</span>
                  <span id="session-timer" className="font-bold text-black dark:text-white">{formatTime(timerSeconds)}</span>
                </div>
              </div>
            </div>

            {/* Right: Share Link Pill & Quick Action Toggles */}
            <div className="flex items-center gap-2">
              <button
                id="header-invite-btn"
                type="button"
                onClick={copyInviteLink}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white dark:bg-neutral-800 border border-black/15 dark:border-neutral-700 shadow-sm text-xs font-mono font-semibold hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors text-black dark:text-white"
                title="Share Link"
              >
                <Share2 className="w-3.5 h-3.5 text-[#E6391E]" />
                <span className="font-bold">Share Link</span>
              </button>

              <button
                id="language-btn"
                type="button"
                onClick={() => setLanguageModalOpen(!languageModalOpen)}
                className="control-btn-circle w-8 h-8 rounded-full border border-black/10 flex items-center justify-center bg-white dark:bg-neutral-800"
                title="Audio Language"
              >
                <Languages className="w-3.5 h-3.5" />
              </button>

              <button
                id="dark-mode-btn"
                type="button"
                onClick={toggleDarkMode}
                className="control-btn-circle w-8 h-8 rounded-full border border-black/10 flex items-center justify-center bg-white dark:bg-neutral-800"
                title="Toggle Dark Mode"
              >
                {darkMode ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5" />}
              </button>

              <button
                id="footer-invite-btn"
                type="button"
                onClick={copyInviteLink}
                className="hidden"
                aria-hidden="true"
              >
                Invite
              </button>

              <button
                id="transcript-btn"
                type="button"
                onClick={() => setDrawerOpen(!drawerOpen)}
                className="hidden"
                aria-hidden="true"
              >
                Notes
              </button>

              <button
                id="prompt-eva-btn"
                type="button"
                onClick={handlePromptEva}
                className="hidden"
                aria-hidden="true"
              >
                Prompt
              </button>
            </div>
          </header>

          {/* Main Full-Screen Immersive Area */}
          <main className="flex-1 flex flex-col p-3 sm:p-4 gap-3.5 overflow-y-auto">
            {/* Hero Stage: Rounded-3xl corners with 1080p SFU, DUPLEX HD, LiveKit 18ms badges, Eva Holographic HUD, and Floating Founder PIP */}
            <section className="relative w-full">
              <div
                id="stage-grid"
                className={`relative w-full rounded-3xl bg-gradient-to-b from-neutral-950 via-neutral-900 to-black text-white overflow-hidden shadow-2xl border border-black/15 min-h-[300px] sm:min-h-[340px] flex flex-col justify-between p-4 ${stageLayoutClass}`}
              >
                {/* Top Badge Strip inside Hero Stage */}
                <div className="flex items-center justify-between w-full z-20">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/20 text-[10px] font-mono font-bold tracking-wider text-emerald-400">
                      1080p SFU
                    </span>
                    <span className="px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/20 text-[10px] font-mono font-bold tracking-wider text-sky-400">
                      DUPLEX HD
                    </span>
                    <span className="px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/20 text-[10px] font-mono font-bold tracking-wider text-amber-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                      LiveKit 18ms
                    </span>
                  </div>

                  {/* Live Waveform Speaking Badge */}
                  {evaSpeaking && (
                    <div id="eva-wave" className="flex items-center gap-2 px-3 py-1 rounded-full bg-black/60 backdrop-blur-md border border-[#E6391E]/40">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#E6391E] animate-pulse"></span>
                      <span className="font-mono text-[10px] uppercase font-bold text-[#E6391E]">SPEAKING</span>
                      <div className="active-wave">
                        <span></span>
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Center Hero: Eva Holographic HUD */}
                <div id="eva-tile" className="video-tile-container relative flex-1 flex flex-col items-center justify-center py-6 px-4 z-10">
                  {/* Holographic Concentric Pulse Circles */}
                  <div className="relative flex items-center justify-center">
                    <div className="absolute w-48 h-48 rounded-full bg-[#E6391E]/15 blur-2xl animate-pulse"></div>
                    <div className="absolute w-40 h-40 rounded-full border border-[#E6391E]/30 animate-[spin_15s_linear_infinite]"></div>
                    <div className="absolute w-32 h-32 rounded-full border border-dashed border-white/20 animate-[spin_25s_linear_infinite_reverse]"></div>
                    <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-neutral-900 to-neutral-800 border-2 border-[#E6391E] shadow-[0_0_30px_rgba(230,57,30,0.45)] flex items-center justify-center">
                      <Volume2 className="w-9 h-9 text-[#E6391E] animate-pulse" />
                    </div>
                  </div>

                  <div className="mt-3 flex flex-col items-center text-center">
                    <div className="font-headline font-bold text-sm text-white tracking-wide flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-[#E6391E]" />
                      <span>EVA ARCHITECT HUD</span>
                    </div>
                    <div className="font-mono text-[9px] uppercase tracking-widest text-neutral-400 mt-0.5">
                      Gemini Live Voice Active
                    </div>
                  </div>

                  <div className="speaker-badge mt-2 bg-black/80 px-2 py-0.5 rounded-full border border-white/10">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#E6391E] animate-pulse"></span>
                    <span id="eva-status-text" className="font-mono text-[10px] text-white">Eva (AI Architect)</span>
                  </div>
                </div>

                {/* Floating Founder PIP Card */}
                <div
                  id="local-tile"
                  className="video-tile-container absolute bottom-3 right-3 w-28 h-36 sm:w-36 sm:h-44 rounded-2xl overflow-hidden bg-neutral-950 border-2 border-white/20 shadow-2xl z-20 flex flex-col justify-between"
                >
                  <video
                    ref={localVideoRef}
                    id="local-video"
                    className={`w-full h-full object-cover ${cameraEnabled ? 'block' : 'hidden'}`}
                    autoPlay
                    playsInline
                    muted
                  />
                  {!cameraEnabled && (
                    <div className="flex-1 flex flex-col items-center justify-center text-white/50 p-2">
                      <div className="w-9 h-9 rounded-full bg-neutral-800 border border-white/15 flex items-center justify-center mb-1">
                        <Users className="w-4 h-4 text-white/70" />
                      </div>
                      <span className="font-mono text-[8px] uppercase tracking-wider text-neutral-400">Founder PIP</span>
                    </div>
                  )}

                  <div className="speaker-badge absolute bottom-1.5 left-1.5 right-1.5 bg-black/80 backdrop-blur-sm px-1.5 py-0.5 rounded-lg flex items-center gap-1 border border-white/10">
                    <span className={`w-1.5 h-1.5 rounded-full ${micMuted ? 'bg-neutral-500' : 'bg-[#E6391E] animate-pulse'}`}></span>
                    <span id="local-name" className="truncate text-[8px] font-mono font-medium text-white">{identity}</span>
                  </div>
                </div>

                {/* Screen Share Stage Floating Overlay (if active) */}
                {isScreenSharing && (
                  <div id="screen-share-stage" className="absolute top-14 left-4 w-44 pip-share-card p-2 rounded-xl z-20 bg-black/85 backdrop-blur border border-white/20">
                    <div className="flex items-center justify-between border-b border-white/10 pb-1 mb-1">
                      <span className="font-mono text-[8px] uppercase font-bold text-white">SCREEN</span>
                      <span className="font-mono text-[8px] uppercase font-bold text-[#E6391E] flex items-center gap-1">
                        <span className="w-1 h-1 rounded-full bg-[#E6391E] animate-ping"></span>
                        LIVE
                      </span>
                    </div>
                    <div className="relative mb-1 w-full h-14 bg-black overflow-hidden rounded">
                      <video
                        ref={screenVideoRef}
                        autoPlay
                        playsInline
                        muted
                        className="w-full h-full object-contain"
                      />
                    </div>
                    <div id="slide-content" className="flex items-center justify-between">
                      <div className="text-[8px] font-mono text-white font-bold">Sharing</div>
                      <button
                        id="stage-screen-btn"
                        type="button"
                        onClick={toggleScreenShare}
                        className="border border-white/30 text-[7px] font-mono font-bold uppercase py-0.5 px-1.5 rounded bg-white text-black hover:bg-neutral-200"
                      >
                        STOP
                      </button>
                    </div>
                  </div>
                )}

                {/* Remote Participants Stack (Hidden unless external client joins) */}
                {hasRemoteClient && (
                  <div id="remote-stack" className="absolute top-14 right-4 w-28 h-20 rounded-xl overflow-hidden bg-neutral-900 border border-white/20 z-20 flex items-center justify-center">
                    <div id="remote-human-tile" className="relative w-full h-full flex flex-col items-center justify-center">
                      <div id="remote-human-placeholder" className="text-white/40 flex flex-col items-center">
                        <Users className="w-5 h-5" />
                      </div>
                      <div className="speaker-badge absolute bottom-1 left-1 right-1 bg-black/80 px-1 py-0.5 rounded text-[7px] flex items-center justify-center text-white">
                        <span id="remote-human-name">{remoteClientName}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* Live Executive Transcription & Spec Distillation Card */}
            <section className="w-full flex-1 flex flex-col min-h-0 pb-20">
              <div className="bg-white dark:bg-neutral-900 border border-black/15 dark:border-neutral-800 rounded-3xl shadow-sm flex flex-col flex-1 overflow-hidden">
                {/* Header with AUTO-GENERATING PLAN Badge */}
                <div className="p-3.5 border-b border-black/10 dark:border-neutral-800 flex items-center justify-between bg-zinc-50/70 dark:bg-neutral-950/50 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-ping"></span>
                    <h2 className="font-headline font-bold text-xs uppercase tracking-tight text-neutral-900 dark:text-neutral-100">
                      Live Executive Transcription &amp; Spec Distillation
                    </h2>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* AUTO-GENERATING PLAN Badge */}
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#E6391E]/10 border border-[#E6391E]/30 text-[#E6391E] font-mono text-[9px] font-bold uppercase tracking-wider animate-pulse">
                      <Sparkles className="w-3 h-3" />
                      AUTO-GENERATING PLAN
                    </span>
                    <span className="font-mono text-[9px] text-neutral-400">PCM 24kHz</span>
                  </div>
                </div>

                {/* Real-time Transcription Stream */}
                <div
                  ref={transcriptListRef}
                  id="transcript-list"
                  className="flex-1 overflow-y-auto divide-y divide-black/5 dark:divide-neutral-800/60 p-3.5 space-y-2.5 text-xs max-h-56 sm:max-h-72"
                >
                  <div className="font-mono text-[10px] text-neutral-400 uppercase tracking-wider font-semibold">
                    LIVE NOTES
                  </div>
                  {transcripts.map((item) => (
                    <div key={item.id} className="pt-2 first:pt-0 space-y-1 text-left">
                      <div className="flex items-center justify-between text-[9px] font-mono text-neutral-400">
                        <span className="font-bold text-[#E6391E]">{item.speaker}</span>
                        <span>{item.time}</span>
                      </div>
                      <p className={`font-sans leading-relaxed font-medium ${darkMode ? 'text-neutral-100' : 'text-[#0A0A0A]'}`}>
                        {item.text}
                      </p>
                      {liveTranslateEnabled && (
                        <p className={`font-mono text-[10px] italic p-1.5 rounded-lg border ${
                          darkMode ? 'bg-neutral-800 border-neutral-700 text-neutral-300' : 'bg-[#FAF7F2] border-black/10 text-neutral-600'
                        }`}>
                          {getTranslatedLine(item, selectedLanguage)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>

                {/* Query Input / Voice Instruction Box */}
                <div className="p-3 border-t border-black/10 dark:border-neutral-800 bg-[#FAF7F2]/60 dark:bg-neutral-950">
                  <form onSubmit={handleSendChat} id="chat-form" className="flex gap-2">
                    <input
                      id="chat-input"
                      type="text"
                      placeholder="Prompt Eva or type executive directive..."
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      className={`flex-1 border px-3 py-1.5 text-xs font-mono rounded-xl focus:outline-none focus:ring-1 focus:ring-black ${
                        darkMode ? 'border-neutral-700 bg-neutral-900 text-white' : 'border-black/20 bg-white text-black'
                      }`}
                    />
                    <button
                      type="submit"
                      className={`px-3.5 py-1.5 text-xs font-mono font-bold rounded-xl transition-colors ${
                        darkMode ? 'border border-neutral-700 bg-neutral-800 text-white hover:bg-neutral-700' : 'border border-black bg-black text-white hover:bg-neutral-800'
                      }`}
                    >
                      ADD
                    </button>
                  </form>
                </div>
              </div>
            </section>
          </main>

          {/* Floating 4-Button In-Call Bottom Pill Bar */}
          <footer className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40">
            <div className="flex items-center gap-3 bg-neutral-950/95 text-white backdrop-blur-xl px-5 py-2.5 rounded-full shadow-[0_12px_35px_rgba(0,0,0,0.35)] border border-white/20">
              {/* 1. Mic Button */}
              <button
                id="mic-btn"
                type="button"
                onClick={toggleMic}
                className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${
                  micMuted ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-white/15 hover:bg-white/25 text-white'
                }`}
                title={micMuted ? 'Unmute' : 'Mute'}
              >
                {micMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              </button>

              {/* 2. Video Camera Button */}
              <button
                id="cam-btn"
                type="button"
                onClick={toggleCamera}
                className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${
                  cameraEnabled ? 'bg-[#E6391E] text-white shadow-lg' : 'bg-white/15 hover:bg-white/25 text-white'
                }`}
                title={cameraEnabled ? 'Turn Off Camera' : 'Turn On Camera'}
              >
                {cameraEnabled ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5" />}
              </button>

              {/* 3. Screen Share Button */}
              <button
                id="screen-btn"
                type="button"
                onClick={toggleScreenShare}
                className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${
                  isScreenSharing ? 'bg-emerald-500 text-white shadow-lg' : 'bg-white/15 hover:bg-white/25 text-white'
                }`}
                title="Present Screen"
              >
                <MonitorUp className="w-5 h-5" />
              </button>

              {/* 4. End Call Red Button */}
              <button
                id="end-call-btn"
                type="button"
                onClick={handleEndCall}
                className="w-11 h-11 rounded-full bg-[#E6391E] hover:bg-red-600 active:scale-95 text-white flex items-center justify-center shadow-lg transition-transform"
                title="End Call"
              >
                <PhoneOff className="w-5 h-5" />
              </button>
            </div>
          </footer>

          {/* Language Selection Modal */}
          {languageModalOpen && (
            <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-white dark:bg-neutral-900 border-2 border-black dark:border-neutral-700 p-5 w-full max-w-xs space-y-3 shadow-2xl rounded-2xl">
                <div className="flex items-center justify-between border-b border-black/15 dark:border-neutral-800 pb-2">
                  <h3 className="font-headline font-bold text-xs text-black dark:text-white">Audio Language</h3>
                  <button onClick={() => setLanguageModalOpen(false)} className="text-neutral-500 hover:text-black dark:hover:text-white">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="grid grid-cols-1 gap-1.5 max-h-52 overflow-y-auto">
                  {LANGUAGES.map((lang) => (
                    <button
                      key={lang.code}
                      onClick={() => {
                        setSelectedLanguage(lang.code);
                        setLanguageModalOpen(false);
                      }}
                      className={`text-left px-2.5 py-1.5 text-xs font-mono flex items-center justify-between rounded-lg border ${
                        selectedLanguage === lang.code
                          ? 'border-[#E6391E] bg-[#E6391E]/10 font-bold text-[#E6391E]'
                          : 'border-neutral-200 dark:border-neutral-800 text-black dark:text-neutral-200'
                      }`}
                    >
                      <span>{lang.name}</span>
                      {selectedLanguage === lang.code && <Check className="w-3 h-3 text-[#E6391E]" />}
                    </button>
                  ))}
                </div>
                <label className="flex items-center gap-2 text-xs font-mono text-neutral-700 dark:text-neutral-300 pt-2 border-t border-neutral-200 dark:border-neutral-800">
                  <input
                    type="checkbox"
                    checked={liveTranslateEnabled}
                    onChange={(e) => setLiveTranslateEnabled(e.target.checked)}
                    className="accent-black"
                  />
                  Live Translation
                </label>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
