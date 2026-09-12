import React, { useState, useEffect } from 'react';
import { TaskDiffResponse } from '../types';
import { mobileApi } from '../api/client';
import { ArrowLeft, FileCode, CheckCircle2, GitCommit, Plus, Minus } from 'lucide-react';

interface Props {
  taskId: string;
  onBack: () => void;
  onPromote: (taskId: string) => void;
}

export const CodeDiffScreen: React.FC<Props> = ({ taskId, onBack, onPromote }) => {
  const [diff, setDiff] = useState<TaskDiffResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi.getTaskDiff(taskId).then((data) => {
      setDiff(data);
      setLoading(false);
    });
  }, [taskId]);

  if (loading || !diff) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Loading diff viewer...</div>;
  }

  const currentFile = diff.files[selectedFile];

  return (
    <div className="space-y-4">
      {/* Top Navigation */}
      <div className="flex items-center justify-between border-b border-card-border pb-3">
        <button onClick={onBack} className="flex items-center gap-1 text-muted hover:text-white font-mono text-xs">
          <ArrowLeft className="w-4 h-4" /> Task Detail
        </button>
        <span className="font-mono text-xs text-accent">04 // CODE DIFF</span>
      </div>

      {/* Diff Stat Summary */}
      <div className="locomotive-card p-3 rounded-lg flex items-center justify-between font-mono text-xs">
        <div className="flex items-center gap-2">
          <GitCommit className="w-4 h-4 text-accent" />
          <span className="text-slate-300">{diff.base_commit} → {diff.head_commit}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-emerald-400 flex items-center"><Plus className="w-3 h-3" />{diff.total_additions}</span>
          <span className="text-red-400 flex items-center"><Minus className="w-3 h-3" />{diff.total_deletions}</span>
        </div>
      </div>

      {/* File Selector Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1 font-mono text-xs">
        {diff.files.map((file, i) => (
          <button
            key={i}
            onClick={() => setSelectedFile(i)}
            className={`px-3 py-1.5 rounded flex items-center gap-1.5 border whitespace-nowrap transition-colors ${
              selectedFile === i
                ? 'bg-accent/10 border-accent text-white'
                : 'border-card-border text-muted hover:border-slate-600'
            }`}
          >
            <FileCode className="w-3.5 h-3.5 text-accent" />
            <span>{file.file_path.split('/').pop()}</span>
          </button>
        ))}
      </div>

      {/* File Header */}
      {currentFile && (
        <div className="locomotive-card rounded-lg overflow-hidden">
          <div className="bg-slate-900 px-3 py-2 border-b border-card-border flex items-center justify-between font-mono text-xs">
            <span className="text-slate-300 font-semibold">{currentFile.file_path}</span>
            <div className="flex items-center gap-2 text-[11px]">
              <span className="text-emerald-400">+{currentFile.additions}</span>
              <span className="text-red-400">-{currentFile.deletions}</span>
            </div>
          </div>
          <pre className="p-3 bg-black/60 font-mono text-[11px] leading-relaxed overflow-x-auto text-slate-300 whitespace-pre">
            {currentFile.patch}
          </pre>
        </div>
      )}

      {/* One-Tap Action */}
      <div className="pt-2">
        <button
          onClick={() => onPromote(taskId)}
          className="w-full py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-semibold flex items-center justify-center gap-2 transition-colors"
        >
          <CheckCircle2 className="w-4 h-4" /> Approve & Proceed to One-Tap Merge
        </button>
      </div>
    </div>
  );
};
