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
        <h2 className="text-3xl font-headline font-bold mt-1 leading-tight text-[#0A0A0A]">
          Connect Instance
        </h2>
        <p className="font-mono text-[11px] text-zinc-500 mt-1">
          Scan the QR code from your local instance to securely connect your workspace.
        </p>
      </div>

      {/* QR Scanner Viewfinder with orange corner brackets */}
      <div className="flex-1 flex flex-col items-center justify-center py-4">
        <div
          onClick={handleSimulateScan}
          className="w-64 h-64 relative rounded-2xl flex flex-col items-center justify-center border border-zinc-200 bg-zinc-50/70 overflow-hidden shadow-sm cursor-pointer hover:border-zinc-400 transition-colors"
          title="Tap to scan or pair"
        >
          {/* 4 Corner brackets */}
          <div className="absolute top-2 left-2 w-9 h-9 border-t-2 border-l-2 border-[#E6391E] rounded-tl-lg z-10" />
          <div className="absolute top-2 right-2 w-9 h-9 border-t-2 border-r-2 border-[#E6391E] rounded-tr-lg z-10" />
          <div className="absolute bottom-2 left-2 w-9 h-9 border-b-2 border-l-2 border-[#E6391E] rounded-bl-lg z-10" />
          <div className="absolute bottom-2 right-2 w-9 h-9 border-b-2 border-r-2 border-[#E6391E] rounded-br-lg z-10" />

          {/* Animated Scanning Beam */}
          {scanning && (
            <div className="absolute inset-x-0 top-0 h-1 bg-[#E6391E] shadow-[0_0_12px_#E6391E] animate-bounce z-20" />
          )}

          {/* Video Viewfinder */}
          <video 
            ref={videoRef}
            className={`absolute inset-0 w-full h-full object-cover z-0 ${cameraActive && !isPaired ? 'block' : 'hidden'}`}
            playsInline
            muted
          />

          {(!cameraActive || isPaired) && (
            <div className="flex flex-col items-center justify-center z-0 p-4 text-center">
              <svg className="w-16 h-16 text-zinc-300 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="7" height="7" />
                <rect x="14" y="3" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" />
                <rect x="14" y="14" width="7" height="7" />
                <path d="M7 7h.01M17 7h.01M7 17h.01M17 17h.01" strokeWidth="3" strokeLinecap="round" />
              </svg>
              <span className="font-mono text-[10px] text-zinc-400">
                Position the QR code within the frame
              </span>
            </div>
          )}

          {cameraError && !isPaired && (
            <div className="absolute inset-x-0 bottom-4 text-center z-10">
              <span className="bg-[#E6391E] text-white text-[9px] px-2 py-1 uppercase font-mono">{cameraError}</span>
            </div>
          )}

          <div className="absolute inset-x-0 bottom-3 text-center z-10 flex flex-col items-center">
            <span className="font-mono text-[9px] text-white bg-black/70 px-2 py-0.5 rounded tracking-widest uppercase">
              {isPaired ? `DEVICE PAIRED: ${payload.device_serial}` : 'SCANNING • ALIGN QR'}
            </span>
          </div>
        </div>

        {/* OR Divider */}
        <div className="w-full flex items-center justify-center gap-3 my-4">
          <div className="flex-1 h-[1px] bg-zinc-200" />
          <span className="font-mono text-[10px] text-zinc-400 font-bold uppercase tracking-widest">
            OR
          </span>
          <div className="flex-1 h-[1px] bg-zinc-200" />
        </div>

        {/* Enter Sync ID manually Pill Button */}
        {onNavigateSAS && (
          <button
            onClick={onNavigateSAS}
            className="w-full py-3 px-4 border border-[#0A0A0A] bg-white text-[#0A0A0A] font-headline text-xs font-bold rounded-xl flex items-center justify-between hover:bg-zinc-50 active:scale-[0.99] transition-all shadow-sm"
          >
            <div className="flex items-center gap-2.5">
              <svg className="w-4 h-4 text-[#E6391E]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="4" width="20" height="16" rx="2" />
                <path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 16h10" />
              </svg>
              <span>Enter Sync ID manually</span>
            </div>
            <span className="text-[#0A0A0A] font-mono text-xs">›</span>
          </button>
        )}

        {/* Security Reassurance Card */}
        <div className="w-full mt-3 border border-zinc-200 bg-zinc-50/80 p-3 rounded-xl flex items-center gap-3">
          <div className="w-7 h-7 border border-zinc-300 rounded-full flex items-center justify-center shrink-0 text-[#0A0A0A] bg-white">
            <svg className="w-3.5 h-3.5 text-[#0A0A0A]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <div>
            <div className="font-headline text-xs font-bold text-[#0A0A0A]">
              Secure Connection
            </div>
            <div className="font-mono text-[10px] text-zinc-500">
              Your data stays on your local instance.
            </div>
          </div>
        </div>
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
            SECURITY CONFIRMATION
          </span>
          <span className="font-mono text-[10px] text-zinc-500 uppercase">
            SECURITY CODE
          </span>
        </div>
        <h2 className="text-4xl font-headline font-bold mt-2 leading-tight text-[#0A0A0A]">
          Security Code
          <br />
          Confirmation
        </h2>
        <p className="font-mono text-[11px] text-zinc-500 mt-1">
          Confirm that the code below matches the code displayed on your desktop screen.
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
