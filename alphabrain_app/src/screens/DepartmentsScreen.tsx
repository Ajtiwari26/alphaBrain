import React, { useState, useEffect } from 'react';
import { ScreenId } from '../types';
import { 
  Code2, 
  ArrowRight, 
  Bot, 
  GitBranch, 
  Plus, 
  Trash2, 
  X, 
  Check, 
  ShieldCheck, 
  Terminal, 
  Layers,
  Inbox,
  Rocket,
  Sliders
} from 'lucide-react';

interface Props {
  onSelectDept?: (screen: ScreenId) => void;
}

interface CustomDepartment {
  id: string;
  name: string;
  category: string;
  description: string;
  assignedModel: string;
  status: string;
  createdAt: string;
}

const STORAGE_KEY = 'alphabrain_custom_departments';

export const DepartmentsScreen: React.FC<Props> = ({ onSelectDept }) => {
  const [customDepts, setCustomDepts] = useState<CustomDepartment[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState('');
  const [category, setCategory] = useState('');
  const [description, setDescription] = useState('');
  const [assignedModel, setAssignedModel] = useState('Gemini 3.1 Pro');

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(customDepts));
    } catch (e) {
      console.warn('Failed to persist custom departments:', e);
    }
  }, [customDepts]);

  const handleCreateDepartment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    const newDept: CustomDepartment = {
      id: `dept_${Date.now()}`,
      name: name.trim(),
      category: category.trim().toUpperCase() || 'AUTONOMOUS DIVISION',
      description: description.trim() || 'Custom autonomous department created by Founder.',
      assignedModel,
      status: 'INITIALIZED',
      createdAt: new Date().toISOString(),
    };

    setCustomDepts((prev) => [newDept, ...prev]);
    setName('');
    setCategory('');
    setDescription('');
    setAssignedModel('Gemini 3.1 Pro');
    setShowCreateModal(false);
  };

  const handleDeleteDepartment = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCustomDepts((prev) => prev.filter((d) => d.id !== id));
  };

  return (
    <div className="flex-1 flex flex-col bg-white text-[#0A0A0A] animate-screen-enter space-y-4 pb-[max(env(safe-area-inset-bottom),5rem)]">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
              ORGANIZATIONAL ARCHITECTURE
            </span>
            <span className="font-mono text-[9px] px-1.5 py-0.2 bg-[#0A0A0A] text-white font-bold uppercase">
              {1 + customDepts.length} DEPARTMENTS
            </span>
          </div>

          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1 font-mono text-[10px] font-bold bg-[#0A0A0A] text-white px-2.5 py-1 hover:bg-[#E6391E] transition-colors border border-[#0A0A0A]"
          >
            <Plus className="w-3 h-3" />
            <span>NEW DEPT</span>
          </button>
        </div>

        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          Departments
        </h2>
        <p className="font-mono text-[11px] text-zinc-500 mt-0.5">
          Engineering & core runtime with founder-defined autonomous divisions
        </p>
      </div>

      {/* Creation Modal / Inline Sheet */}
      {showCreateModal && (
        <div className="border-2 border-[#0A0A0A] p-4 bg-zinc-50 space-y-3 animate-screen-enter">
          <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-2">
            <span className="font-mono text-xs font-bold text-[#E6391E] flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5" />
              CREATE NEW DEPARTMENT
            </span>
            <button
              onClick={() => setShowCreateModal(false)}
              className="text-zinc-500 hover:text-[#0A0A0A]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <form onSubmit={handleCreateDepartment} className="space-y-3 font-mono text-xs">
            <div>
              <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-1">
                Department Name *
              </label>
              <input
                type="text"
                placeholder="e.g. Design & UI Systems, Growth & Distribution"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full bg-white border border-[#0A0A0A] p-2 text-xs text-[#0A0A0A] outline-none focus:border-[#E6391E]"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-1">
                  Division Tag
                </label>
                <input
                  type="text"
                  placeholder="e.g. UI/UX ENGINE"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full bg-white border border-[#0A0A0A] p-2 text-xs text-[#0A0A0A] outline-none focus:border-[#E6391E]"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-1">
                  Assigned AI Model
                </label>
                <select
                  value={assignedModel}
                  onChange={(e) => setAssignedModel(e.target.value)}
                  className="w-full bg-white border border-[#0A0A0A] p-2 text-xs text-[#0A0A0A] outline-none focus:border-[#E6391E]"
                >
                  <option value="Gemini 3.1 Pro">Gemini 3.1 Pro High</option>
                  <option value="Claude Opus 4.6">Claude Opus 4.6 Thinking</option>
                  <option value="Gemini Flash 2.0">Gemini Flash 2.0</option>
                  <option value="Claude Sonnet 3.7">Claude Sonnet 3.7 Thinking</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-1">
                Core Mission / Responsibilities
              </label>
              <textarea
                placeholder="Describe what tasks and workflows this autonomous department will handle..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="w-full bg-white border border-[#0A0A0A] p-2 text-xs text-[#0A0A0A] outline-none focus:border-[#E6391E]"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="px-3 py-1.5 border border-[#0A0A0A] bg-white text-[#0A0A0A] hover:bg-zinc-100"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 border border-[#0A0A0A] bg-[#E6391E] text-white font-bold hover:bg-red-700 flex items-center gap-1"
              >
                <Check className="w-3.5 h-3.5" />
                Spawn Department
              </button>
            </div>
          </form>
        </div>
      )}

      {/* CORE 01: Engineering & Tech (Dedicated Primary Card) */}
      <div className="border-2 border-[#0A0A0A] p-4 bg-white space-y-3">
        {/* Title row */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold text-[#E6391E]">01 //</span>
            <h3 className="font-headline text-lg font-bold text-[#0A0A0A]">
              Engineering & Tech
            </h3>
          </div>
          <span className="font-mono text-[9px] font-bold px-2 py-0.5 border uppercase bg-emerald-100 text-emerald-800 border-emerald-300">
            OPERATIONAL
          </span>
        </div>

        {/* Category & Description */}
        <div className="space-y-1">
          <div className="font-mono text-[9px] text-zinc-400 font-bold uppercase tracking-wider">
            HEADLESS EXECUTION & RUNTIME
          </div>
          <p className="text-xs text-zinc-600 font-sans leading-relaxed">
            Headless coding daemons, isolated Git worktrees, and Vercel/Android deployment pipelines running autonomously on host Mac.
          </p>
        </div>

        {/* Assigned Agents */}
        <div className="pt-2 border-t border-zinc-200">
          <span className="font-mono text-[10px] text-zinc-400 uppercase block mb-1.5 font-bold">
            Assigned Agents:
          </span>
          <div className="flex items-center gap-2 flex-wrap font-mono text-[10px]">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-zinc-100 border border-zinc-200 text-zinc-800">
              <Bot className="w-3 h-3 text-zinc-500" />
              <strong>Worker Etta-1</strong>
              <span className="text-zinc-500">(Gemini 3.1 Pro)</span>
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-zinc-100 border border-zinc-200 text-zinc-800">
              <Bot className="w-3 h-3 text-zinc-500" />
              <strong>Research Etta-2</strong>
              <span className="text-zinc-500">(Flash High)</span>
            </span>
          </div>
        </div>

        {/* Quick Jump Subsystems Grid */}
        <div className="pt-2 border-t border-zinc-200">
          <span className="font-mono text-[10px] text-zinc-400 uppercase block mb-1.5 font-bold">
            Department Subsystems:
          </span>
          <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
            <button
              onClick={() => onSelectDept?.('worktrees')}
              className="p-2 border border-[#0A0A0A] bg-zinc-50 hover:bg-[#0A0A0A] hover:text-white transition-colors flex flex-col items-center text-center gap-1"
            >
              <GitBranch className="w-3.5 h-3.5 text-[#E6391E]" />
              <span className="font-bold">Worktrees</span>
              <span className="text-[9px] text-zinc-500">1 Active</span>
            </button>

            <button
              onClick={() => onSelectDept?.('triage')}
              className="p-2 border border-[#0A0A0A] bg-zinc-50 hover:bg-[#0A0A0A] hover:text-white transition-colors flex flex-col items-center text-center gap-1"
            >
              <Inbox className="w-3.5 h-3.5 text-[#E6391E]" />
              <span className="font-bold">Triage</span>
              <span className="text-[9px] text-zinc-500">1 Pending</span>
            </button>

            <button
              onClick={() => onSelectDept?.('deployments')}
              className="p-2 border border-[#0A0A0A] bg-zinc-50 hover:bg-[#0A0A0A] hover:text-white transition-colors flex flex-col items-center text-center gap-1"
            >
              <Rocket className="w-3.5 h-3.5 text-[#E6391E]" />
              <span className="font-bold">Deploy</span>
              <span className="text-[9px] text-zinc-500">Live ↗</span>
            </button>
          </div>
        </div>

        {/* Bottom runtime status */}
        <div className="pt-2 border-t border-zinc-200 flex items-center justify-between font-mono text-[10px] text-zinc-500">
          <span>HOST RUNTIME: NODE 22 • PY 3.12</span>
          <button
            onClick={() => onSelectDept?.('tech_dept')}
            className="flex items-center gap-1 font-bold text-[#0A0A0A] hover:text-[#E6391E] transition-colors"
          >
            <span>Full Tech Console</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Dynamic Founder-Created Custom Departments */}
      {customDepts.length > 0 && (
        <div className="space-y-3">
          <div className="font-mono text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
            FOUNDER-SPAWNED DIVISIONS ({customDepts.length})
          </div>

          {customDepts.map((dept, idx) => (
            <div
              key={dept.id}
              className="border border-[#0A0A0A] p-4 bg-white hover:bg-zinc-50 transition-colors space-y-2.5 relative"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-[#E6391E]">
                    0{idx + 2} //
                  </span>
                  <h4 className="font-headline text-base font-bold text-[#0A0A0A]">
                    {dept.name}
                  </h4>
                </div>

                <div className="flex items-center gap-2">
                  <span className="font-mono text-[8px] font-bold px-1.5 py-0.5 border uppercase bg-zinc-100 text-zinc-800 border-zinc-300">
                    {dept.status}
                  </span>
                  <button
                    onClick={(e) => handleDeleteDepartment(dept.id, e)}
                    className="text-zinc-400 hover:text-[#E6391E] transition-colors p-1"
                    title="Archive Division"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <div className="font-mono text-[9px] text-zinc-400 font-bold uppercase tracking-wider">
                  {dept.category}
                </div>
                <p className="text-xs text-zinc-600 font-sans leading-relaxed">
                  {dept.description}
                </p>
              </div>

              <div className="pt-2 border-t border-zinc-200 flex items-center justify-between font-mono text-[10px]">
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-zinc-100 border border-zinc-200 text-zinc-800 text-[9px]">
                  <Bot className="w-2.5 h-2.5 text-zinc-500" />
                  <strong>Model:</strong> {dept.assignedModel}
                </span>

                <span className="text-[9px] text-zinc-400">
                  Created {new Date(dept.createdAt).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State when no custom departments yet */}
      {customDepts.length === 0 && (
        <div
          onClick={() => setShowCreateModal(true)}
          className="border border-dashed border-zinc-300 p-4 text-center cursor-pointer hover:border-[#0A0A0A] hover:bg-zinc-50 transition-colors"
        >
          <div className="font-mono text-xs font-bold text-zinc-600 flex items-center justify-center gap-1.5 mb-1">
            <Plus className="w-3.5 h-3.5 text-[#E6391E]" />
            SPAWN ADDITIONAL DEPARTMENTS
          </div>
          <p className="font-sans text-[11px] text-zinc-400">
            Click here or the top button to create dedicated divisions for Design, Growth, Auditing, etc.
          </p>
        </div>
      )}

      {/* Governance Security Banner */}
      <div className="border border-zinc-300 p-3 bg-zinc-50 font-mono text-[10px] text-zinc-600 space-y-1">
        <div className="flex items-center justify-between font-bold text-[#0A0A0A]">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-[#E6391E]" />
            FOUNDER ORG GOVERNANCE
          </span>
          <span>AUTONOMOUS WORKTREE DISPATCH</span>
        </div>
        <p className="text-[9px] text-zinc-500 leading-normal">
          Engineering & Tech handles all active coding and deployment. Only the Founder can instantiate or retire operational departments.
        </p>
      </div>
    </div>
  );
};

