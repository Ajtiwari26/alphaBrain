import React, { useState, useEffect } from 'react';
import { desktopApi } from '../api/client';
import { ProjectItem } from '../types';
import { FolderGit2, RefreshCw, CheckCircle2, Clock } from 'lucide-react';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SkeletonTable } from '../components/ui/Skeleton';

export const ProjectsScreen: React.FC = () => {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchProjects = () => {
    setLoading(true);
    desktopApi
      .getProjects()
      .then((data) => {
        setProjects(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load projects:', err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-6 animate-screen-enter">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#E6391E] font-bold uppercase tracking-widest">
              PORTFOLIO // DESKTOP WORKSPACES
            </span>
            <span className="text-neutral-300">•</span>
            <span className="font-mono text-xs text-neutral-500 uppercase">
              LOCAL GIT REPOSITORIES
            </span>
          </div>
          <h1 className="text-3xl font-bold font-sans tracking-tight mt-1 text-[#0A0A0A]">
            Project Repositories
          </h1>
          <p className="font-mono text-xs text-neutral-500 mt-1">
            Registered development repositories and isolated active worktrees on macOS host
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchProjects}
            className="flex items-center gap-2 px-4 py-2 border border-[#0A0A0A] bg-white font-mono text-xs font-bold btn-tactile hover-lift transition-smooth hover:border-[#E6391E]"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#E6391E]' : ''}`} />
            <span>REFRESH</span>
          </button>
        </div>
      </div>

      {/* Projects List Card */}
      <div className="border border-[#0A0A0A] bg-white">
        <div className="grid grid-cols-12 px-6 py-3 border-b border-[#0A0A0A] bg-neutral-50 font-mono text-xs text-neutral-500 font-bold uppercase">
          <div className="col-span-5">Repository Name</div>
          <div className="col-span-4">Filesystem Path</div>
          <div className="col-span-2">Last Activity</div>
          <div className="col-span-1 text-right">Status</div>
        </div>

        {loading ? (
          <div className="space-y-4">
            <div className="p-4 border-b border-neutral-100 flex items-center justify-center bg-neutral-50/50">
              <LoadingSpinner size="md" label="Scanning local filesystem for git workspaces..." />
            </div>
            <SkeletonTable rows={4} />
          </div>
        ) : projects.length === 0 ? (
          <div className="p-12 text-center font-mono text-xs text-neutral-400">
            No local repositories detected.
          </div>
        ) : (
          <div className="divide-y divide-neutral-200">
            {projects.map((p) => {
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
                  className="grid grid-cols-12 px-6 py-4 items-center hover:bg-neutral-50 transition-smooth hover:translate-x-1 cursor-pointer"
                >
                  <div className="col-span-5 flex items-center gap-3">
                    <div className="w-8 h-8 border border-[#0A0A0A] bg-neutral-100 flex items-center justify-center transition-transform duration-200 group-hover:scale-105">
                      <FolderGit2 className="w-4 h-4 text-[#E6391E]" />
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-[#0A0A0A]">{p.name}</h3>
                      <span className="font-mono text-[10px] text-neutral-400">GIT REPOSITORY</span>
                    </div>
                  </div>

                  <div className="col-span-4 font-mono text-xs text-neutral-600 truncate pr-4">
                    {p.path}
                  </div>

                  <div className="col-span-2 font-mono text-xs text-neutral-500 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-neutral-400" />
                    <span>{timeLabel}</span>
                  </div>

                  <div className="col-span-1 flex items-center justify-end">
                    {p.is_active ? (
                      <span className="flex items-center gap-1.5 font-mono text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-300 px-2 py-0.5">
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                        ACTIVE
                      </span>
                    ) : (
                      <span className="font-mono text-[10px] text-neutral-400 border border-neutral-200 px-2 py-0.5">
                        IDLE
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer statistics summary */}
      <div className="border border-[#0A0A0A] bg-neutral-50 p-4 font-mono text-xs flex justify-between items-center">
        <span className="text-neutral-500">LOCAL WORKSPACE INVENTORY</span>
        <span className="font-bold text-[#0A0A0A]">
          {projects.length} REPOSITORIES DISCOVERED
        </span>
      </div>
    </div>
  );
};
