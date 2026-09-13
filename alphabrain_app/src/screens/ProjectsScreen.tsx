import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';

interface ProjectItem {
  name: string;
  path: string;
  mtime: number;
  is_active: boolean;
}

export const ProjectsScreen: React.FC = () => {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi
      .getProjects()
      .then((data) => {
        setProjects(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[75vh]">
      <div className="border-b border-[#0A0A0A] pb-3">
        <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
          PORTFOLIO // DESKTOP WORKSPACES
        </span>
        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Projects
        </h2>
      </div>

      <div className="flex-1 flex flex-col divide-y divide-[#0A0A0A] my-4 overflow-y-auto max-h-[60vh]">
        {loading ? (
          <div className="p-8 text-center font-mono text-xs text-zinc-400">
            Scanning local repositories...
          </div>
        ) : projects.length === 0 ? (
          <div className="p-8 text-center font-mono text-xs text-zinc-400">
            No local repositories found.
          </div>
        ) : (
          projects.map((p) => {
            const ageHours = Math.round((Date.now() / 1000 - p.mtime) / 3600);
            const timeLabel =
              ageHours < 1
                ? 'JUST NOW'
                : ageHours < 24
                ? `${ageHours}H AGO`
                : `${Math.round(ageHours / 24)}D AGO`;

            return (
              <div
                key={p.name}
                className="py-4 px-1 flex flex-col justify-between hover:bg-zinc-50 cursor-pointer transition-colors"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-headline font-bold text-[#0A0A0A]">
                    {p.name}
                  </h3>
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${
                      p.is_active ? 'bg-[#E6391E] animate-pulse' : 'bg-zinc-300'
                    }`}
                  />
                </div>
                <div className="flex items-center justify-between mt-2 font-mono text-[10px] text-zinc-400">
                  <span className="truncate max-w-[200px]">{p.path}</span>
                  <span className="uppercase font-semibold text-zinc-500">{timeLabel}</span>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="border-t border-[#0A0A0A] pt-4 flex items-center justify-between font-mono text-xs">
        <span className="text-zinc-500">ACTIVE WORKSPACES</span>
        <span className="font-bold text-[#0A0A0A]">{projects.length} REPOSITORIES</span>
      </div>
    </div>
  );
};
