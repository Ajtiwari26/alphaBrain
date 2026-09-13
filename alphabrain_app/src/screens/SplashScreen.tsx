import React, { useEffect } from 'react';

interface Props {
  onContinue?: () => void;
}

export const SplashScreen: React.FC<Props> = ({ onContinue }) => {
  useEffect(() => {
    // Automatically transition to Founder Access after 2.0s
    const timer = setTimeout(() => {
      onContinue?.();
    }, 2000);

    return () => clearTimeout(timer);
  }, [onContinue]);

  return (
    <div className="flex-1 flex flex-col justify-between items-center bg-white text-[#0A0A0A] min-h-screen pt-16 pb-6 px-6 select-none relative">
      {/* Top Status Area Space */}
      <div className="w-full flex justify-between items-center opacity-0 pointer-events-none">
        <span className="font-mono text-xs">09:41</span>
        <span className="font-mono text-xs">5G</span>
      </div>

      {/* Center: AlphaBrain 3D Neural Wireframe Mesh + Bold Logotype */}
      <div className="flex flex-col items-center justify-center -mt-12">
        <div className="w-56 h-56 flex items-center justify-center mb-6">
          <img
            src="/alpha_symbol.svg"
            alt="AlphaBrain 3D Neural Wireframe"
            className="w-52 h-52 object-contain animate-logo-breathe"
          />
        </div>

        <h1 className="text-5xl font-headline font-bold text-center tracking-tight text-[#0A0A0A]">
          AlphaBrain
        </h1>
      </div>

      {/* Bottom: POWERED BY DeployMate */}
      <div className="flex flex-col items-center justify-center space-y-2 pb-2">
        <span className="font-mono text-[9px] text-zinc-400 tracking-[0.35em] uppercase font-medium">
          POWERED BY
        </span>

        <img
          src="/deploymate_logo.png"
          alt="DeployMate"
          className="h-8 object-contain"
        />

        {/* Home Indicator Bar */}
        <div className="w-32 h-1 bg-[#0A0A0A] rounded-full mt-4" />
      </div>
    </div>
  );
};
