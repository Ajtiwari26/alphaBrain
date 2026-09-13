import React, { useState } from 'react';

interface Props {
  onAuthenticated?: () => void;
}

export const AuthScreen: React.FC<Props> = ({ onAuthenticated }) => {
  const [authed, setAuthed] = useState(false);

  const handleAuth = () => {
    setAuthed(true);
    setTimeout(() => {
      onAuthenticated?.();
    }, 400);
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-4">
        <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
          01 — ACCESS
        </span>
        <h2 className="text-4xl font-headline font-bold mt-2 leading-tight text-[#0A0A0A]">
          Founder
          <br />
          Access
        </h2>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center py-12">
        <div className="w-28 h-28 border-2 border-[#0A0A0A] p-4 flex items-center justify-center mb-6">
          <svg
            className={`w-16 h-16 transition-transform ${authed ? 'scale-110' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke={authed ? '#E6391E' : '#0A0A0A'}
            strokeWidth="1.5"
          >
            <path
              d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"
              strokeLinecap="square"
            />
            <circle cx="9" cy="9" r="1" fill={authed ? '#E6391E' : '#0A0A0A'} />
            <circle cx="15" cy="9" r="1" fill={authed ? '#E6391E' : '#0A0A0A'} />
            <path d="M12 11v3M9 16c1 .67 2 .67 3 .67s2 0 3-.67" />
          </svg>
        </div>
        <span className="font-mono text-[11px] text-zinc-500 tracking-wider">
          {authed ? 'FOUNDER VERIFIED // ACCESS GRANTED' : 'BIOMETRIC SECURE HARDWARE'}
        </span>
      </div>

      <div>
        <div
          onClick={handleAuth}
          className="border border-[#0A0A0A] p-5 flex items-center justify-between hover:bg-black hover:text-white cursor-pointer transition-colors group"
        >
          <span className="font-medium text-base">
            {authed ? 'Identity Verified' : 'Tap to authenticate'}
          </span>
          <span className="text-xl text-[#E6391E] font-bold group-hover:translate-x-1 transition-transform">
            ↗
          </span>
        </div>
      </div>
    </div>
  );
};
