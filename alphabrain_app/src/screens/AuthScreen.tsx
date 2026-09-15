import React, { useState, useEffect, useRef } from 'react';
import { hashPin } from '../types';

interface Props {
  onAuthenticated?: () => void;
  onNavigateEnroll?: () => void;
}

export const AuthScreen: React.FC<Props> = ({ onAuthenticated, onNavigateEnroll }) => {
  const [pin, setPin] = useState('');
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [biometricScanning, setBiometricScanning] = useState(false);

  const timersRef = useRef<number[]>([]);

  useEffect(() => {
    return () => {
      timersRef.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  const triggerAuthSuccess = () => {
    setAuthed(true);
    setError(null);
    const t = window.setTimeout(() => {
      onAuthenticated?.();
    }, 450);
    timersRef.current.push(t);
  };

  const handleDigit = async (digit: string) => {
    if (authed) return;
    if (error) setError(null);

    if (pin.length < 4) {
      const nextPin = pin + digit;
      setPin(nextPin);

      if (nextPin.length === 4) {
        try {
          const inputHash = await hashPin(nextPin);
          const storedHash = localStorage.getItem('alphabrain_master_pin_hash');

          let isValid = false;
          if (storedHash) {
            isValid = inputHash === storedHash;
          } else {
            // Uninitialized fresh instance: verify against default initial hash
            const defaultInitialHash = await hashPin('1337');
            isValid = inputHash === defaultInitialHash;
          }

          if (isValid) {
            triggerAuthSuccess();
          } else {
            setError('INVALID MASTER PIN • ACCESS DENIED');
            const t = window.setTimeout(() => {
              setPin('');
              setError(null);
            }, 1200);
            timersRef.current.push(t);
          }
        } catch {
          setError('CRYPTO VERIFICATION ERROR');
        }
      }
    }
  };

  const handleBackspace = () => {
    if (authed) return;
    if (error) setError(null);
    setPin((prev) => prev.slice(0, -1));
  };

  const handleAuto = async () => {
    if (authed) return;
    const isDev = Boolean(import.meta.env?.DEV);
    if (!isDev) {
      setError('AUTO-FILL DISABLED IN PRODUCTION');
      return;
    }

    // In DEV mode: auto-fill test PIN and verify cryptographic hash
    const testPin = '1337';
    setPin(testPin);
    const testHash = await hashPin(testPin);
    const storedHash = localStorage.getItem('alphabrain_master_pin_hash');

    if (!storedHash || storedHash === testHash) {
      triggerAuthSuccess();
    } else {
      setError('DEV AUTO-PIN MISMATCHES ENROLLED HASH');
    }
  };

  const handleBiometricTouch = () => {
    if (authed) return;
    const isDev = Boolean(import.meta.env?.DEV);
    setBiometricScanning(true);

    if (!isDev) {
      const t = window.setTimeout(() => {
        setBiometricScanning(false);
        setError('HARDWARE BIOMETRIC REGISTRATION REQUIRED • ENTER PIN');
      }, 600);
      timersRef.current.push(t);
      return;
    }

    const t = window.setTimeout(async () => {
      setBiometricScanning(false);
      const storedHash = localStorage.getItem('alphabrain_master_pin_hash');
      if (storedHash) {
        triggerAuthSuccess();
      } else {
        setError('NO MASTER PIN ENROLLED • ENROLL VIA MC-02A');
      }
    }, 600);
    timersRef.current.push(t);
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-4">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
            01 — ACCESS
          </span>
          <span className="font-mono text-[10px] text-zinc-500 uppercase">
            MC-02B • ACCESS GATE
          </span>
        </div>
        <h2 className="text-4xl font-headline font-bold mt-2 leading-tight text-[#0A0A0A]">
          Founder
          <br />
          Access
        </h2>
      </div>

      {/* Middle Section: Touch ID Box & 4 Square PIN Boxes */}
      <div className="flex-1 flex flex-col items-center justify-center py-4 space-y-4">
        {/* Touch ID Box */}
        <div
          onClick={handleBiometricTouch}
          className={`w-24 h-24 border-2 p-3 flex flex-col items-center justify-center cursor-pointer transition-all ${
            authed
              ? 'border-[#E6391E] bg-red-50/20 scale-105'
              : biometricScanning
              ? 'border-[#E6391E] bg-zinc-50 scale-95'
              : 'border-[#0A0A0A] hover:bg-zinc-50 active:scale-95'
          }`}
          title="Touch ID Sensor • Click to simulate biometric recognition"
        >
          <svg
            className={`w-12 h-12 transition-colors ${
              authed || biometricScanning ? 'text-[#E6391E]' : 'text-[#0A0A0A]'
            }`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path
              d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"
              strokeLinecap="square"
            />
            {/* Fingerprint ridges */}
            <path d="M12 7c-2.76 0-5 2.24-5 5 0 2.2 1.42 4.07 3.4 4.74" />
            <path d="M12 10a2 2 0 0 0-2 2c0 1.5 1 2.5 2 3" />
            <path d="M15 12c0-1.66-1.34-3-3-3" />
            <path d="M12 17v2" />
            <path d="M17 12c0 2.5-1.5 4.5-3.5 5" />
          </svg>
        </div>

        <div className="text-center">
          <span className="font-mono text-[10px] text-zinc-500 tracking-wider uppercase block">
            {authed
              ? 'FOUNDER VERIFIED • ACCESS GRANTED'
              : biometricScanning
              ? 'TOUCH ID SCANNING...'
              : 'TOUCH ID SENSOR • BIOMETRIC EMULATION'}
          </span>
        </div>

        {/* 4 Square PIN Boxes */}
        <div className="flex items-center justify-center gap-3 pt-2">
          {[0, 1, 2, 3].map((index) => {
            const hasValue = pin.length > index;
            const isCurrent = pin.length === index && !authed;
            return (
              <div
                key={index}
                className={`w-14 h-14 border-2 flex items-center justify-center font-mono text-2xl font-bold transition-all ${
                  authed
                    ? 'border-[#E6391E] bg-red-50/30 text-[#E6391E]'
                    : isCurrent
                    ? 'border-[#E6391E] bg-zinc-50'
                    : hasValue
                    ? 'border-[#0A0A0A] bg-white text-[#0A0A0A]'
                    : 'border-zinc-300 bg-white text-zinc-300'
                }`}
              >
                {hasValue ? (
                  authed ? pin[index] : '●'
                ) : (
                  <span className="text-zinc-300 text-sm">_</span>
                )}
              </div>
            );
          })}
        </div>

        {error && (
          <div className="font-mono text-xs text-[#E6391E] font-bold tracking-wider animate-pulse">
            {error}
          </div>
        )}
      </div>

      {/* Keypad with [AUTO], [0], [⌫] */}
      <div className="space-y-2">
        <div className="grid grid-cols-3 gap-2">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((digit) => (
            <button
              key={digit}
              onClick={() => handleDigit(digit)}
              disabled={authed}
              className="h-12 border border-[#0A0A0A] font-headline text-lg font-bold hover:bg-[#0A0A0A] hover:text-white active:scale-95 transition-all flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {digit}
            </button>
          ))}
          <button
            onClick={handleAuto}
            disabled={authed}
            className="h-12 border border-[#0A0A0A] font-mono text-xs font-bold text-[#E6391E] hover:bg-[#E6391E] hover:text-white active:scale-95 transition-all flex items-center justify-center tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
          >
            AUTO
          </button>
          <button
            onClick={() => handleDigit('0')}
            disabled={authed}
            className="h-12 border border-[#0A0A0A] font-headline text-lg font-bold hover:bg-[#0A0A0A] hover:text-white active:scale-95 transition-all flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
          >
            0
          </button>
          <button
            onClick={handleBackspace}
            disabled={authed}
            className="h-12 border border-[#0A0A0A] font-mono text-sm font-bold text-zinc-700 hover:bg-[#0A0A0A] hover:text-white active:scale-95 transition-all flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ⌫
          </button>
        </div>

        {/* Action Footers */}
        <div className="flex items-center justify-between pt-1">
          {onNavigateEnroll && (
            <button
              onClick={onNavigateEnroll}
              className="font-mono text-[10px] text-zinc-500 hover:text-[#E6391E] transition-colors uppercase tracking-wider"
            >
              Enroll Master PIN (MC-02A) ↗
            </button>
          )}
          <button
            onClick={handleBiometricTouch}
            className="font-mono text-[10px] text-zinc-500 hover:text-[#0A0A0A] transition-colors uppercase tracking-wider ml-auto"
          >
            Touch ID Fallback ↗
          </button>
        </div>
      </div>
    </div>
  );
};
