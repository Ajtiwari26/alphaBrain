import React, { useState, useEffect } from 'react';
import { DeploymentTarget } from '../types';
import { mobileApi } from '../api/client';

export const DeploymentsScreen: React.FC = () => {
  const [deployments, setDeployments] = useState<DeploymentTarget[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi.getDeployments().then((data) => {
      setDeployments(data);
      setLoading(false);
    });
  }, []);

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          12 // PRODUCTION TARGETS
        </span>
        <h2 className="text-3xl font-headline font-bold text-[#0A0A0A] mt-1">
          Deployments
        </h2>
      </div>

      <div className="flex-1 py-4 font-mono text-xs space-y-3 divide-y divide-zinc-200">
        {loading ? (
          <div className="p-8 text-center text-zinc-400">Loading live deployments...</div>
        ) : deployments.length === 0 ? (
          <div className="p-8 text-center text-zinc-400">No active deployments registered.</div>
        ) : (
          deployments.map((dep) => (
            <div key={dep.id} className="pt-3 first:pt-0 space-y-1">
              <div className="flex justify-between items-center">
                <span className="font-bold text-[#0A0A0A] text-sm">{dep.service_name}</span>
                <span className="text-[10px] px-1.5 py-0.5 border border-[#0A0A0A] bg-zinc-50 font-bold uppercase text-[#E6391E]">
                  {dep.status}
                </span>
              </div>
              <div className="flex justify-between text-zinc-500 text-[11px]">
                <span>{dep.provider} // {dep.environment}</span>
                <span className="text-[#E6391E] font-bold">{dep.commit_sha}</span>
              </div>
              <div className="text-zinc-400 text-[10px] truncate">
                {dep.live_url}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex justify-between items-center font-mono text-xs">
        <span className="text-zinc-500">HOST STATUS: ONLINE</span>
        <span
          onClick={() => {
            setLoading(true);
            mobileApi.getDeployments().then((data) => {
              setDeployments(data);
              setLoading(false);
            });
          }}
          className="font-bold text-[#E6391E] underline cursor-pointer hover:text-black"
        >
          REFRESH TARGETS ↗
        </span>
      </div>
    </div>
  );
};
