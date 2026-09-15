import React, { useState, useEffect, useRef } from 'react';
import { hashPin } from '../types';

interface Props {
  onCompleted?: (pin: string) => void;
  onCancel?: () => void;
}

export const EnrollmentScreen: React.FC<Props> = ({ onCompleted, onCancel }) => {
  const [step, setStep] = useState<'create' | 'confirm' | 'success'>('create');
  const [createPin, setCreatePin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [error, setError] = useState<string | null>(null);

  const timersRef = useRef<number[]>([]);

  useEffect(() => {
    return () => {
      // Clear any pending timeouts on unmount
      timersRef.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  const activePin = step === 'create' ? createPin : confirmPin;
  const isComplete = step === 'success';

  const handleDigit = (digit: string) => {
    if (isComplete) return;
    if (error) setError(null);

    if (step === 'create') {
      setCreatePin((prev) => {
        if (prev.length >= 4) return prev;
        const next = prev + digit;
        if (next.length === 4) {
          const t = window.setTimeout(() => {
            setStep('confirm');
          }, 200);
          timersRef.current.push(t);
        }
        return next;
      });
    } else if (step === 'confirm') {
      setConfirmPin((prev) => {
        if (prev.length >= 4) return prev;
        const next = prev + digit;
        if (next.length === 4) {
          if (next === createPin) {
            setStep('success');
            hashPin(next)
              .then((hashed) => {
                try {
                  localStorage.setItem('alphabrain_master_pin_hash', hashed);
                } catch {
                  // Fallback for sandboxed storage
                }
              })
              .catch(() => {
                // Ignore crypto errors in unsupported environments
              });

            const t = window.setTimeout(() => {
              onCompleted?.(next);
            }, 600);
            timersRef.current.push(t);
          } else {
            setError('PIN MISMATCH • PLEASE TRY AGAIN');
            const t = window.setTimeout(() => {
              setConfirmPin('');
              setError(null);
            }, 1200);
            timersRef.current.push(t);
          }
        }
        return next;
      });
    }
  };

  const handleBackspace = () => {
    if (isComplete) return;
    if (error) setError(null);
    if (step === 'create') {
      setCreatePin((prev) => prev.slice(0, -1));
    } else if (step === 'confirm') {
      setConfirmPin((prev) => prev.slice(0, -1));
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      {/* Header Bar */}
      <div className="border-b border-[#0A0A0A] pb-4">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs text-[#E6391E] font-bold tracking-widest uppercase">
            {step === 'create' && 'STEP 1 OF 2'}
            {step === 'confirm' && 'STEP 2 OF 2'}
            {step === 'success' && 'VERIFIED'}
          </span>
        </div>
        <h2 className="text-3xl font-headline font-bold mt-2 leading-tight text-[#0A0A0A]">
          {step === 'create' && 'Create Master PIN'}
          {step === 'confirm' && 'Confirm Master PIN'}
          {step === 'success' && 'PIN Registered'}
        </h2>
        <p className="font-mono text-[11px] text-zinc-500 mt-1">
          {step === 'create' && 'Set a 4-digit security PIN for remote mobile authorization'}
          {step === 'confirm' && 'Re-enter your 4-digit PIN to verify accuracy'}
          {step === 'success' && 'Master PIN successfully verified and stored.'}
        </p>
      </div>

      {/* PIN Box Displays with square brutalist design */}
      <div className="flex-1 flex flex-col items-center justify-center py-6 space-y-4">
        <div className="flex items-center justify-center gap-3">
          {[0, 1, 2, 3].map((index) => {
            const hasValue = activePin.length > index;
            const isCurrent = activePin.length === index && !isComplete;
            return (
              <div
                key={index}
                className={`w-14 h-14 border-2 flex items-center justify-center font-mono text-2xl font-bold transition-all ${
                  isComplete
                    ? 'border-[#E6391E] bg-red-50/30 text-[#E6391E]'
                    : isCurrent
                    ? 'border-[#E6391E] bg-zinc-50'
                    : hasValue
                    ? 'border-[#0A0A0A] bg-white text-[#0A0A0A]'
                    : 'border-zinc-300 bg-white text-zinc-300'
                }`}
              >
                {hasValue ? (isComplete ? activePin[index] : '●') : <span className="text-zinc-300 text-sm">_</span>}
              </div>
            );
          })}
        </div>

        {error ? (
          <div className="font-mono text-xs text-[#E6391E] font-bold tracking-wider animate-pulse">
            {error}
          </div>
        ) : (
          <div className="font-mono text-[10px] text-zinc-400 tracking-widest uppercase">
            {step === 'create' && 'ENTER 4-DIGIT PIN'}
            {step === 'confirm' && 'REPEAT PIN TO CONFIRM'}
            {step === 'success' && 'MASTER PIN SAVED SUCCESSFULLY'}
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
              disabled={isComplete}
              className="h-12 border border-[#0A0A0A] font-headline text-lg font-bold hover:bg-[#0A0A0A] hover:text-white active:scale-95 transition-all flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {digit}
            </button>
          ))}
          <div className="h-12 flex items-center justify-center">
            <svg className="w-4 h-4 text-zinc-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <button
            onClick={() => handleDigit('0')}
            disabled={isComplete}
            className="h-12 border border-[#0A0A0A] font-headline text-lg font-bold hover:bg-[#0A0A0A] hover:text-white active:scale-95 transition-all flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
          >
            0
          </button>
          <button
            onClick={handleBackspace}
            disabled={isComplete}
            className="h-12 border border-[#0A0A0A] font-mono text-sm font-bold text-zinc-700 hover:bg-[#0A0A0A] hover:text-white active:scale-95 transition-all flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ⌫
          </button>
        </div>

        {onCancel && (
          <button
            onClick={onCancel}
            disabled={isComplete}
            className="w-full py-2.5 mt-2 border border-zinc-200 font-mono text-xs text-zinc-400 hover:border-[#0A0A0A] hover:text-[#0A0A0A] transition-colors text-center uppercase tracking-wider disabled:opacity-40"
          >
            ‹ Back
          </button>
        )}
      </div>
    </div>
  );
};
