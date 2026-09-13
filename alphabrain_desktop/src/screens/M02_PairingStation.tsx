import React, { useState, useEffect } from 'react';
import { QrCode, RefreshCw, Copy, Check, Shield, Smartphone, KeyRound, ArrowRight } from 'lucide-react';
import { QrPayloadV2, ScreenId } from '../types';

interface Props {
  onNavigate: (screen: ScreenId) => void;
}

export const M02_PairingStation: React.FC<Props> = ({ onNavigate }) => {
  const [countdown, setCountdown] = useState(120);
  const [copied, setCopied] = useState(false);
  const [sasCode, setSasCode] = useState('8492');
  const [pairedDevice, setPairedDevice] = useState<{
    model: string;
    ip: string;
    verified: boolean;
  } | null>(null);

  const [payload, setPayload] = useState<QrPayloadV2>({
    v: 2,
    type: 'CLOUD_PROVISION',
    backend_url: 'https://api.alphabrain.live',
    session_token: 'jwt_sec_prov_92f038102bc4910284712093847291',
    node_id: 'AB-MACBOOK-PRO-M4',
    node_ed25519_pubkey: 'MCowBQYDK2VwAyEA2r4F/AB9y9nJzZ1sH9E6x2T61bKk8V9q7f5d3a1b0c=',
    issued_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 120000).toISOString(),
    sig: 'MEQCIB8Z3s9gK8lY1bH/vP5s9kL3d7f9a1b0c8e2g4i6k8mAAiB6v8x2z4b6=',
    sas_code: '8492',
  });

  const rotateToken = () => {
    const newSas = Math.floor(1000 + Math.random() * 9000).toString();
    setSasCode(newSas);
    setCountdown(120);
    setPayload({
      v: 2,
      type: 'CLOUD_PROVISION',
      backend_url: 'https://api.alphabrain.live',
      session_token: `jwt_sec_prov_${Math.random().toString(36).substring(2, 15)}_${Date.now()}`,
      node_id: 'AB-MACBOOK-PRO-M4',
      node_ed25519_pubkey: 'MCowBQYDK2VwAyEA2r4F/AB9y9nJzZ1sH9E6x2T61bKk8V9q7f5d3a1b0c=',
      issued_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 120000).toISOString(),
      sig: 'MEQCIB8Z3s9gK8lY1bH/vP5s9kL3d7f9a1b0c8e2g4i6k8mAAiB6v8x2z4b6=',
      sas_code: newSas,
    });
  };

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          rotateToken();
          return 120;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const simulatePair = () => {
    setPairedDevice({
      model: 'iPhone 16 Pro Max (Founder Device)',
      ip: '192.168.1.142',
      verified: true,
    });
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8 bg-white text-[#0A0A0A] font-sans">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-4 flex justify-between items-end">
        <div>
          <span className="text-xs font-mono tracking-widest uppercase bg-[#0A0A0A] text-white px-2 py-0.5 font-bold">
            Screen M-02
          </span>
          <h1 className="text-3xl font-bold font-mono tracking-tight mt-2">
            PAIRING STATION & DYNAMIC QR GATEWAY
          </h1>
          <p className="text-sm text-neutral-600 mt-1">
            Scan to pair Founder Mobile Companion via Cloud Provisioning Protocol v2 with Short Authentication String (SAS).
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="border border-[#0A0A0A] px-3 py-1 bg-neutral-100 font-mono text-xs flex items-center gap-2">
            <span className="text-neutral-500">AUTO-ROTATION:</span>
            <span className="font-bold text-[#E6391E]">{countdown}s</span>
          </div>
          <button
            onClick={rotateToken}
            className="p-1.5 border border-[#0A0A0A] hover:bg-neutral-100"
            title="Rotate Session Token Now"
          >
            <RefreshCw className="w-4 h-4 text-[#0A0A0A]" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
        {/* Left Column: QR Code & SAS Verification (5 cols) */}
        <div className="md:col-span-5 border-2 border-[#0A0A0A] p-6 space-y-5 bg-white flex flex-col items-center text-center">
          <div className="w-full flex justify-between items-center text-xs font-mono border-b border-neutral-200 pb-2">
            <span className="font-bold uppercase tracking-wider text-[#E6391E]">DYNAMIC V2 QR</span>
            <span className="text-neutral-500">TTL: 120s</span>
          </div>

          {/* Render Brutalist Styled QR Graphic */}
          <div className="w-64 h-64 border-2 border-[#0A0A0A] p-3 bg-white flex flex-col justify-between relative shadow-[4px_4px_0px_0px_rgba(10,10,10,1)]">
            <svg
              viewBox="0 0 100 100"
              className="w-full h-full"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              {/* Corner position markers */}
              <rect x="5" y="5" width="26" height="26" stroke="#0A0A0A" strokeWidth="4" fill="none" />
              <rect x="11" y="11" width="14" height="14" fill="#0A0A0A" />
              
              <rect x="69" y="5" width="26" height="26" stroke="#0A0A0A" strokeWidth="4" fill="none" />
              <rect x="75" y="11" width="14" height="14" fill="#0A0A0A" />

              <rect x="5" y="69" width="26" height="26" stroke="#0A0A0A" strokeWidth="4" fill="none" />
              <rect x="11" y="75" width="14" height="14" fill="#0A0A0A" />

              {/* Center AlphaBrain Mark */}
              <rect x="42" y="42" width="16" height="16" fill="#E6391E" />

              {/* Data matrix pattern */}
              <rect x="36" y="10" width="8" height="6" fill="#0A0A0A" />
              <rect x="48" y="14" width="6" height="8" fill="#0A0A0A" />
              <rect x="58" y="8" width="6" height="12" fill="#0A0A0A" />
              <rect x="10" y="36" width="6" height="8" fill="#0A0A0A" />
              <rect x="20" y="44" width="8" height="6" fill="#0A0A0A" />
              <rect x="12" y="56" width="12" height="6" fill="#0A0A0A" />
              <rect x="72" y="38" width="16" height="6" fill="#0A0A0A" />
              <rect x="80" y="48" width="8" height="14" fill="#0A0A0A" />
              <rect x="38" y="66" width="6" height="16" fill="#0A0A0A" />
              <rect x="48" y="76" width="14" height="8" fill="#0A0A0A" />
              <rect x="68" y="70" width="8" height="12" fill="#0A0A0A" />
              <rect x="80" y="78" width="10" height="10" fill="#0A0A0A" />
            </svg>

            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-10">
              <QrCode className="w-32 h-32 text-black" />
            </div>
          </div>

          {/* Short Authentication String (SAS) Verification */}
          <div className="w-full border border-[#0A0A0A] bg-neutral-50 p-3 space-y-1">
            <span className="text-[10px] font-mono text-neutral-500 uppercase tracking-wider block">
              SAS Confirmation Code (TOFU Security §14.2.5)
            </span>
            <div className="text-2xl font-mono font-bold tracking-[0.25em] text-[#E6391E]">
              {sasCode}
            </div>
            <p className="text-[10px] text-neutral-600">
              Verify this 4-digit code matches the prompt on your mobile screen before accepting.
            </p>
          </div>

          {/* Quick Simulation Trigger */}
          <button
            onClick={simulatePair}
            className="w-full py-2 border border-[#0A0A0A] bg-neutral-100 hover:bg-neutral-200 text-xs font-mono uppercase font-bold"
          >
            Simulate Founder Scan
          </button>
        </div>

        {/* Right Column: Protocol Payload & Security Guarantees (7 cols) */}
        <div className="md:col-span-7 space-y-6">
          {/* Paired Device Status if active */}
          {pairedDevice ? (
            <div className="border-2 border-emerald-800 bg-emerald-50 p-4 space-y-2">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2 text-emerald-900 font-mono text-xs font-bold uppercase">
                  <Smartphone className="w-4 h-4 text-emerald-700" />
                  <span>Founder Mobile Companion Linked</span>
                </div>
                <span className="text-[10px] font-mono bg-emerald-200 text-emerald-900 px-2 py-0.5 font-bold uppercase">
                  Authenticated
                </span>
              </div>
              <div className="text-xs font-mono text-emerald-950 grid grid-cols-2 gap-2 pt-1">
                <div>Model: <strong className="text-black">{pairedDevice.model}</strong></div>
                <div>Tunnel IP: <strong className="text-black">{pairedDevice.ip}</strong></div>
              </div>
              <div className="pt-2">
                <button
                  onClick={() => onNavigate('M03_CommandNode')}
                  className="w-full flex items-center justify-center gap-2 py-2 border border-emerald-900 bg-emerald-700 text-white hover:bg-emerald-800 text-xs font-mono font-bold uppercase tracking-wider"
                >
                  <span>Open M-03 Command Node Dashboard</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ) : (
            <div className="border border-[#0A0A0A] p-4 bg-neutral-50 flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                <span className="font-bold">Awaiting Founder Mobile Scan...</span>
              </div>
              <span className="text-neutral-500 text-[11px]">Single-use claim</span>
            </div>
          )}

          {/* Signed Payload Inspector */}
          <div className="border border-[#0A0A0A] p-4 space-y-3">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-[#E6391E]" />
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider">
                  Cloud Provisioning Payload (JSON v2)
                </h3>
              </div>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-xs font-mono px-2 py-1 border border-[#0A0A0A] hover:bg-neutral-100"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                <span>{copied ? 'Copied' : 'Copy JSON'}</span>
              </button>
            </div>

            <pre className="bg-[#0A0A0A] text-emerald-400 p-3 font-mono text-[11px] overflow-x-auto leading-relaxed border border-neutral-700">
              {JSON.stringify(payload, null, 2)}
            </pre>
          </div>

          {/* Security Guarantees Matrix */}
          <div className="border border-[#0A0A0A] p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-[#E6391E]" />
              <h3 className="text-xs font-mono font-bold uppercase tracking-wider">
                Cryptographic Invariants (§14.2.5)
              </h3>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="p-2 border border-neutral-200 bg-neutral-50">
                <span className="font-bold block text-[#0A0A0A]">Replay Prevention</span>
                <span className="text-[11px] text-neutral-500">
                  Single-use JWT consumed atomically on first claim with 5min TTL.
                </span>
              </div>
              <div className="p-2 border border-neutral-200 bg-neutral-50">
                <span className="font-bold block text-[#0A0A0A]">Screen-Share Safety</span>
                <span className="text-[11px] text-neutral-500">
                  Second scan attempt fails immediately even if stream is hijacked.
                </span>
              </div>
              <div className="p-2 border border-neutral-200 bg-neutral-50">
                <span className="font-bold block text-[#0A0A0A]">MITM Resistance</span>
                <span className="text-[11px] text-neutral-500">
                  Ed25519 signature validated against TOFU pinned public key.
                </span>
              </div>
              <div className="p-2 border border-neutral-200 bg-neutral-50">
                <span className="font-bold block text-[#0A0A0A]">Instant Revocation</span>
                <span className="text-[11px] text-neutral-500">
                  DELETE /api/auth/devices terminates JWT and disconnects instantly.
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
