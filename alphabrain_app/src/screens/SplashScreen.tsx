import React from 'react';

interface Props {
  onContinue?: () => void;
}

export const SplashScreen: React.FC<Props> = ({ onContinue }) => {
  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="flex-1 flex flex-col items-center justify-center px-6 -mt-4">
        <div className="w-56 h-56 flex items-center justify-center mb-6">
          <img
            src="/alpha_symbol.svg"
            alt="AlphaBrain Neural Symbol"
            className="w-48 h-48 object-contain"
          />
        </div>
        <h1 className="text-4xl font-headline font-bold text-center tracking-tight text-[#0A0A0A]">
          AlphaBrain
        </h1>
        <span className="font-mono text-[11px] text-[#E6391E] font-bold tracking-widest mt-2 uppercase">
          DeployMate Locomotive
        </span>
      </div>

      <div className="pt-6">
        <div
          onClick={onContinue}
          className="border border-[#0A0A0A] p-4 text-center cursor-pointer hover:bg-black hover:text-white transition-colors group"
        >
          <span className="font-mono text-[10px] text-zinc-500 group-hover:text-zinc-300 tracking-widest block">
            POWERED BY
          </span>
          <div className="flex items-center justify-center gap-2 mt-1">
            <span className="font-mono text-xs font-bold tracking-wider">
              ENTER COMMAND CENTER
            </span>
            <span className="text-[#E6391E] font-bold group-hover:text-white group-hover:translate-x-1 transition-transform">
              ↗
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
