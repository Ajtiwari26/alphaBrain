import React, { useState, useEffect, useRef } from 'react';
import { ProvisioningPayload } from '../types';

interface QRProps {
  onSynced?: () => void;
  onNavigateSAS?: () => void;
}

export const QRProvisioningScreen: React.FC<QRProps> = ({ onSynced, onNavigateSAS }) => {
  const [scanning, setScanning] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const [payload, setPayload] = useState<ProvisioningPayload>({
    device_serial: '10BF5P2AZF0010T',
    tunnel_port: 8000,
    daemon_version: '2.4.0',
    sas_token: 'DELTA-7942-OMEGA',
    status: 'scanning',
  });

  const timersRef = useRef<number[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const scanLoopRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);

  // Bind stream to video element when cameraActive becomes true and ref is mounted
  useEffect(() => {
    if (cameraActive && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current;
      videoRef.current.play().catch(() => {});
    }
  }, [cameraActive]);

  const startCamera = async () => {
    try {
      setCameraError(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
      });
      if (!isMountedRef.current) {
        stream.getTracks().forEach(t => t.stop());
        return;
      }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(() => {});
      }
      setCameraActive(true);
      startQRScanner();
    } catch (err: any) {
      if (isMountedRef.current) {
        setCameraError(err.message || 'Camera access denied');
        setCameraActive(false);
      }
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
    if (scanLoopRef.current) {
      cancelAnimationFrame(scanLoopRef.current);
      scanLoopRef.current = null;
    }
  };

  const startQRScanner = () => {
    // Instantiate detector once outside animation frame loop
    // @ts-ignore
    const detector = ('BarcodeDetector' in window) ? new window.BarcodeDetector({ formats: ['qr_code'] }) : null;

    const scan = async () => {
      if (!isMountedRef.current || !streamRef.current) return;
      if (videoRef.current && videoRef.current.readyState >= 2) {
        if (detector) {
          try {
            const barcodes = await detector.detect(videoRef.current);
            if (!isMountedRef.current || !streamRef.current) return;
            if (barcodes.length > 0) {
              handlePairingSuccess();
              return; // Stop scanning upon successful detection
            }
          } catch (e) {
            // Ignore detector frame drop errors
          }
        }
      }
      if (isMountedRef.current && streamRef.current) {
        scanLoopRef.current = requestAnimationFrame(scan);
      }
    };
    scanLoopRef.current = requestAnimationFrame(scan);
  };

  useEffect(() => {
    isMountedRef.current = true;
    startCamera();
    return () => {
      isMountedRef.current = false;
      stopCamera();
      timersRef.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  const handlePairingSuccess = () => {
    setScanning(false);
    setPayload((prev) => ({ ...prev, status: 'paired' }));
    stopCamera();
    onSynced?.();
  };

  const handleSimulateScan = () => {
    setScanning(true);
    const t = window.setTimeout(() => {
      handlePairingSuccess();
    }, 800);
    timersRef.current.push(t);
  };

  const isPaired = payload.status === 'paired';

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-4">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
            MC-03 • PROVISIONING
          </span>
          <span className="font-mono text-[10px] text-zinc-500 uppercase">
            PORT {payload.tunnel_port} • TUNNEL
          </span>
        </div>
        <h2 className="text-4xl font-headline font-bold mt-2 leading-tight text-[#0A0A0A]">
          QR Remote
          <br />
          Provisioning
        </h2>
        <p className="font-mono text-[11px] text-zinc-500 mt-1">
          Scan desktop terminal QR to establish end-to-end encrypted remote bridge
        </p>
      </div>

      {/* QR Scanner Viewfinder with red-orange corner brackets */}
      <div className="flex-1 flex flex-col items-center justify-center py-6">
        <div className="w-64 h-64 relative flex flex-col items-center justify-center border border-dashed border-zinc-200 bg-zinc-50/50 overflow-hidden">
          {/* 4 Corner brackets */}
          <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-[#E6391E] z-10" />
          <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-[#E6391E] z-10" />
          <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-[#E6391E] z-10" />
          <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-[#E6391E] z-10" />

          {/* Animated Scanning Beam */}
          {scanning && (
            <div className="absolute inset-x-0 top-0 h-1 bg-[#E6391E] shadow-[0_0_8px_#E6391E] animate-bounce z-20" />
          )}

          {/* Video Viewfinder - always mounted so videoRef is always valid */}
          <video 
            ref={videoRef}
            className={`absolute inset-0 w-full h-full object-cover z-0 ${cameraActive && !isPaired ? 'block' : 'hidden'}`}
            playsInline
            muted
          />

          {(!cameraActive || isPaired) && (
            <div className="w-36 h-36 border border-[#0A0A0A] bg-white p-2.5 grid grid-cols-4 gap-1 items-center justify-items-center mb-2 z-0 opacity-30">
              <div className="w-6 h-6 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#E6391E]" />
              <div className="w-6 h-6 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#0A0A0A]" />
              <div className="w-4 h-4 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#E6391E]" />
              <div className="w-4 h-4 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#0A0A0A]" />
              <div className="w-6 h-6 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#0A0A0A]" />
              <div className="w-3 h-3 bg-[#0A0A0A]" />
              <div className="w-6 h-6 bg-[#0A0A0A]" />
            </div>
          )}

          {cameraError && !isPaired && (
            <div className="absolute inset-x-0 bottom-4 text-center z-10">
              <span className="bg-red-500 text-white text-[9px] px-2 py-1 uppercase">{cameraError}</span>
            </div>
          )}

          <div className="absolute inset-x-0 bottom-4 text-center z-10 flex flex-col items-center">
            <span className="font-mono text-[9px] text-white bg-black/60 px-1 tracking-widest uppercase">
              {isPaired ? `DEVICE PAIRED: ${payload.device_serial}` : 'WAITING FOR SCAN • ALIGN QR'}
            </span>
            <span className="font-mono text-[10px] text-[#E6391E] bg-white/90 px-1 font-bold mt-0.5">
              {isPaired ? 'TUNNEL ACTIVE • ADB REVERSE' : 'READY FOR HANDSHAKE'}
            </span>
          </div>
        </div>

        {/* Security Parameters Badge */}
        <div className="w-full mt-4 border border-[#0A0A0A] p-3 divide-y divide-zinc-200">
          <div className="flex items-center justify-between pb-1.5 font-mono text-[10px]">
            <span className="text-zinc-500">PEER SERIAL</span>
            <span className="font-bold text-[#0A0A0A]">{payload.device_serial}</span>
          </div>
          <div className="flex items-center justify-between py-1.5 font-mono text-[10px]">
            <span className="text-zinc-500">ENCRYPTION</span>
            <span className="font-bold text-[#0A0A0A]">ECDH P-256 + AES-GCM</span>
          </div>
          <div className="flex items-center justify-between pt-1.5 font-mono text-[10px]">
            <span className="text-zinc-500">BRIDGE PORT</span>
            <span className="font-bold text-[#E6391E]">127.0.0.1:{payload.tunnel_port}</span>
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="space-y-2">
        <button
          onClick={handleSimulateScan}
          className="w-full border border-[#0A0A0A] p-4 bg-[#0A0A0A] text-white font-headline text-sm font-bold flex items-center justify-between hover:bg-zinc-800 active:scale-[0.99] transition-all"
        >
          <span>{scanning ? 'Pairing Hardware Tunnel...' : isPaired ? 'Re-verify Hardware Tunnel' : 'Confirm Hardware Pairing'}</span>
          <span className="text-[#E6391E] font-mono text-base">↗</span>
        </button>

        {onNavigateSAS && (
          <button
            onClick={onNavigateSAS}
            className="w-full border border-zinc-300 p-3 bg-white text-[#0A0A0A] font-mono text-xs font-semibold flex items-center justify-between hover:border-[#0A0A0A] transition-colors"
          >
            <span>Switch to SAS Verification (MC-03B)</span>
            <span className="text-zinc-500">↗</span>
          </button>
        )}
      </div>
    </div>
  );
};

interface SASProps {
  onVerified?: () => void;
  onNavigateQR?: () => void;
}

export const SASVerificationScreen: React.FC<SASProps> = ({ onVerified, onNavigateQR }) => {
  const [verified, setVerified] = useState(false);
  const [rejected, setRejected] = useState(false);

  const timersRef = useRef<number[]>([]);

  useEffect(() => {
    return () => {
      timersRef.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  const handleConfirm = () => {
    setVerified(true);
    setRejected(false);
    const t = window.setTimeout(() => {
      onVerified?.();
    }, 400);
    timersRef.current.push(t);
  };

  const handleReject = () => {
    setRejected(true);
    setVerified(false);
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-4">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
            MC-03B • SAS VERIFICATION
          </span>
          <span className="font-mono text-[10px] text-zinc-500 uppercase">
            DIFFIE-HELLMAN KEY
          </span>
        </div>
        <h2 className="text-4xl font-headline font-bold mt-2 leading-tight text-[#0A0A0A]">
          Short Auth
          <br />
          String (SAS)
        </h2>
        <p className="font-mono text-[11px] text-zinc-500 mt-1">
          Verify cryptographic short authentication string with desktop terminal
        </p>
      </div>

      {/* Main SAS Display */}
      <div className="flex-1 flex flex-col items-center justify-center py-6 space-y-6">
        {/* SAS Token Box */}
        <div className="w-full border-2 border-[#0A0A0A] p-6 text-center bg-zinc-50/50">
          <span className="font-mono text-[10px] text-zinc-400 tracking-widest uppercase block mb-2">
            TERMINAL VERIFICATION STRING
          </span>
          <div className="font-mono text-2xl font-bold tracking-wider text-[#0A0A0A] py-3 bg-white border border-[#0A0A0A]">
            <span className="text-[#E6391E]">DELTA</span>-7942-<span className="text-[#0A0A0A]">OMEGA</span>
          </div>
          <span className="font-mono text-[10px] text-zinc-500 tracking-wide mt-3 block">
            SHA256: 7f83b165...e26a8e41
          </span>
        </div>

        {/* Verification Status */}
        <div className="w-full">
          {verified ? (
            <div className="p-3 bg-zinc-100 border border-[#0A0A0A] text-center font-mono text-xs text-[#0A0A0A] font-bold">
              ✓ SAS MATCH CONFIRMED • CHANNEL TRUSTED
            </div>
          ) : rejected ? (
            <div className="p-3 bg-red-50 border border-[#E6391E] text-center font-mono text-xs text-[#E6391E] font-bold">
              ⚠ SAS MISMATCH REJECTED • SESSION TERMINATED
            </div>
          ) : (
            <div className="p-3 border border-dashed border-zinc-300 text-center font-mono text-[11px] text-zinc-600">
              Does this code match the string shown on your AlphaBrain Desktop terminal?
            </div>
          )}
        </div>
      </div>

      {/* Action Footer */}
      <div className="space-y-2">
        <button
          onClick={handleConfirm}
          disabled={verified}
          className="w-full border border-[#0A0A0A] p-4 bg-[#0A0A0A] text-white font-headline text-sm font-bold flex items-center justify-between hover:bg-zinc-800 active:scale-[0.99] transition-all disabled:opacity-50"
        >
          <span>Confirm Match (Trust Host)</span>
          <span className="text-[#E6391E] font-mono text-base">↗</span>
        </button>

        <button
          onClick={handleReject}
          disabled={verified}
          className="w-full border border-[#E6391E] p-3 bg-white text-[#E6391E] font-mono text-xs font-bold hover:bg-red-50 transition-colors text-center uppercase tracking-wider"
        >
          Mismatch • Reject Connection
        </button>

        {onNavigateQR && (
          <button
            onClick={onNavigateQR}
            className="w-full py-2 font-mono text-[10px] text-zinc-500 hover:text-[#0A0A0A] transition-colors text-center uppercase tracking-wider"
          >
            Back to QR Provisioning ↗
          </button>
        )}
      </div>
    </div>
  );
};
