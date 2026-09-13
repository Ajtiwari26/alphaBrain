import React, { useState } from 'react';

interface Props {
  onAuthenticated?: () => void;
}

export const AuthScreen: React.FC<Props> = ({ onAuthenticated }) => {
  const [pin, setPin] = useState<string>('');
  const [authed, setAuthed] = useState(false);
  const [errorShake, setErrorShake] = useState(false);

  const handleKeyPress = (num: string) => {
    if (authed) return;
    if (pin.length < 4) {
      const nextPin = pin + num;
      setPin(nextPin);
      if (nextPin.length === 4) {
        // Any 4 digit PIN or 2026 succeeds for the founder
        triggerSuccess();
      }
    }
  };

  const handleBackspace = () => {
    if (authed) return;
    setPin((prev) => prev.slice(0, -1));
  };

  const triggerSuccess = () => {
    setAuthed(true);
    setTimeout(() => {
      onAuthenticated?.();
    }, 450);
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[80vh] px-2">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-3 flex items-center justify-between">
        <div>
          <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
            02 // ACCESS GATE
          </span>
          <h2 className="text-2xl font-headline font-bold mt-1 leading-tight text-[#0A0A0A]">
            Founder Access
          </h2>
        </div>
        <span className="font-mono text-[10px] font-bold px-2 py-0.5 border border-[#0A0A0A] bg-zinc-50 text-[#E6391E]">
          STAGE 2/3
        </span>
      </div>

      {/* Main PIN & Biometric Visual */}
      <div className="flex-1 flex flex-col items-center justify-center py-4">
        {/* Biometric Fingerprint Box */}
        <div
          onClick={triggerSuccess}
          className={`w-24 h-24 border-2 border-[#0A0A0A] p-3 flex flex-col items-center justify-center mb-5 cursor-pointer transition-all duration-300 card-tactile ${
            authed ? 'bg-black text-white border-black scale-105' : 'bg-white hover:bg-zinc-50'
          }`}
        >
          <svg
            className={`w-12 h-12 transition-transform ${authed ? 'scale-110 stroke-[#E6391E]' : 'stroke-[#0A0A0A]'}`}
            viewBox="0 0 24 24"
            fill="none"
            strokeWidth="1.5"
          >
            <path
              d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"
              strokeLinecap="square"
            />
            <circle cx="9" cy="9" r="1.5" fill={authed ? '#E6391E' : '#0A0A0A'} />
            <circle cx="15" cy="9" r="1.5" fill={authed ? '#E6391E' : '#0A0A0A'} />
            <path d="M12 11v3M9 16c1 .67 2 .67 3 .67s2 0 3-.67" />
          </svg>
          <span className="font-mono text-[8px] mt-1 text-zinc-400 font-semibold tracking-wider">
            TOUCH ID
          </span>
        </div>

        {/* PIN Indicators */}
        <div className="flex items-center gap-3 mb-6">
          {[0, 1, 2, 3].map((idx) => {
            const isFilled = pin.length > idx || authed;
            return (
              <div
                key={idx}
                className={`w-3.5 h-3.5 border border-[#0A0A0A] transition-all duration-200 ${
                  isFilled
                    ? 'bg-[#E6391E] border-[#E6391E] scale-110'
                    : 'bg-white'
                }`}
              />
            );
          })}
        </div>

        <span className="font-mono text-[11px] text-zinc-500 tracking-wider text-center">
          {authed
            ? 'FOUNDER VERIFIED // ACCESS GRANTED'
            : 'ENTER 4-DIGIT PIN OR TAP TOUCH ID'}
        </span>

        {/* Tactile Keypad */}
        <div className="w-full max-w-[260px] grid grid-cols-3 gap-2 mt-6">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((num) => (
            <button
              key={num}
              onClick={() => handleKeyPress(num)}
              className="h-12 border border-[#0A0A0A] font-headline font-bold text-lg flex items-center justify-center hover:bg-black hover:text-white transition-colors btn-tactile bg-white"
            >
              {num}
            </button>
          ))}
          <button
            onClick={triggerSuccess}
            className="h-12 border border-[#0A0A0A] font-mono text-[9px] text-[#E6391E] font-bold flex items-center justify-center hover:bg-black hover:text-white transition-colors btn-tactile bg-white"
          >
            AUTO
          </button>
          <button
            onClick={() => handleKeyPress('0')}
            className="h-12 border border-[#0A0A0A] font-headline font-bold text-lg flex items-center justify-center hover:bg-black hover:text-white transition-colors btn-tactile bg-white"
          >
            0
          </button>
          <button
            onClick={handleBackspace}
            className="h-12 border border-[#0A0A0A] font-mono text-xs text-zinc-500 font-bold flex items-center justify-center hover:bg-black hover:text-white transition-colors btn-tactile bg-white"
          >
            ⌫
          </button>
        </div>
      </div>

      {/* Instant Unlock Bar */}
      <div className="pt-3 border-t border-[#0A0A0A]">
        <button
          onClick={triggerSuccess}
          className="w-full border border-[#0A0A0A] p-3.5 flex items-center justify-between hover:bg-black hover:text-white cursor-pointer transition-colors group btn-tactile bg-white"
        >
          <span className="font-mono text-xs font-bold text-[#0A0A0A] group-hover:text-white">
            {authed ? 'Identity Verified // Unlocking...' : 'Instant Founder Biometric Unlock'}
          </span>
          <span className="text-base text-[#E6391E] font-bold group-hover:text-white group-hover:translate-x-1 transition-transform">
            ↗
          </span>
        </button>
      </div>
    </div>
  );
};
