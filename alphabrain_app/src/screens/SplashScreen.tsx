import React from 'react';

interface Props {
  onContinue?: () => void;
}

export const SplashScreen: React.FC<Props> = ({ onContinue }) => {
  // Splash screen remains visible until founder taps anywhere to proceed

  return (
    <div 
      onClick={onContinue}
      className="flex-1 flex flex-col justify-between items-center bg-white text-[#0A0A0A] min-h-screen pt-[max(env(safe-area-inset-top),var(--android-safe-top,0px),3.5rem)] pb-[max(env(safe-area-inset-bottom),var(--android-safe-bottom,0px),4.5rem)] px-6 select-none relative cursor-pointer"
    >
      {/* Top Status Area Space */}
      <div className="w-full flex justify-between items-center opacity-0 pointer-events-none">
        <span className="font-mono text-xs">09:41</span>
        <span className="font-mono text-xs">5G</span>
      </div>

      {/* Center: AlphaBrain 3D Neural Wireframe Mesh + Bold Logotype + Subtitle */}
      <div className="flex flex-col items-center justify-center my-auto">
        <div className="w-48 h-48 flex items-center justify-center mb-5">
          <img
            src="/alphabrain_logo.svg"
            alt="AlphaBrain 3D Neural Mesh"
            className="w-44 h-44 object-contain animate-logo-breathe"
          />
        </div>

        <h1 className="text-4xl font-headline font-bold text-center tracking-tight text-[#0A0A0A]">
          AlphaBrain
        </h1>
        <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.25em] mt-2 font-medium">
          A Brighter Tomorrow For Your Ideas
        </p>
      </div>

      {/* Bottom: Co-Branding with POWERED BY + DeployMate Stacked SVG Logo */}
      <div className="flex flex-col items-center justify-center space-y-2.5 text-center">
        <span className="font-mono text-[11px] text-zinc-400 tracking-[0.25em] uppercase font-semibold">
          AlphaBrain is powered by DeployMate
        </span>
        <img
          src="/deploymate_logo.svg"
          alt="DeployMate"
          className="w-32 h-auto object-contain"
        />
      </div>
    </div>
  );
};
