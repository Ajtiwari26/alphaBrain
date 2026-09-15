import React, { useState, useEffect } from 'react';
import { 
  Key, 
  Eye, 
  EyeOff, 
  Copy, 
  Check, 
  Plus, 
  Trash2, 
  Edit3, 
  Lock, 
  Search, 
  X, 
  ShieldCheck 
} from 'lucide-react';

export interface EnvSecret {
  id: string;
  key: string;
  value: string;
  comment: string;
  department: string;
  updatedAt: string;
}

const STORAGE_KEY = 'alphabrain_env_vault_secrets';

const INITIAL_SECRETS: EnvSecret[] = [
  {
    id: 'sec_1',
    key: 'ANTHROPIC_API_KEY',
    value: 'sk-ant-api03-live-alpha-prod-98741b8a9c2e4f01',
    comment: 'Primary production key used by Claude Opus 4.6 for architectural reviews and OC-EDS multi-agent governance.',
    department: 'Engineering & Tech',
    updatedAt: '2026-09-15T14:30:00Z',
  },
  {
    id: 'sec_2',
    key: 'GEMINI_API_KEY',
    value: 'AIzaSyA4Q9xK1b8N6_alphaBrain_worker_live',
    comment: 'Token for Gemini 3.1 Pro worker daemons and automated triage code repair cycles.',
    department: 'Engineering & Tech',
    updatedAt: '2026-09-15T16:00:00Z',
  },
  {
    id: 'sec_3',
    key: 'STITCH_API_KEY',
    value: 'AQ.Ab8RN6_ajay_stitch_mcp_master_token_2026',
    comment: "Ajay's Stitch MCP account key for automated design tokens, UI variant generation, and screen mocking.",
    department: 'Engineering & Tech',
    updatedAt: '2026-09-14T10:15:00Z',
  },
  {
    id: 'sec_4',
    key: 'MONGODB_URI',
    value: 'mongodb+srv://alphabrain:cluster0.live.mongodb.net/alphabrain_prod?retryWrites=true&w=majority',
    comment: 'Production MongoDB Atlas connection string for multi-agent knowledge graph, sessions, and telemetry.',
    department: 'All Departments',
    updatedAt: '2026-09-13T08:20:00Z',
  },
  {
    id: 'sec_5',
    key: 'GITHUB_TOKEN',
    value: 'ghp_AlphaBrainAutoWorkerWorktreeDeploy998124',
    comment: 'Fine-grained Personal Access Token for headless Git worktree commits, PR creation, and branch merging.',
    department: 'Engineering & Tech',
    updatedAt: '2026-09-16T01:00:00Z',
  },
  {
    id: 'sec_6',
    key: 'LIVEKIT_API_SECRET',
    value: 'env_livekit_sec_eva_voice_bridge_audio_synthesis',
    comment: 'WebRTC audio synthesis secret for Eva Voice CTO low-latency bidirectional telephony room.',
    department: 'Executive & Eva',
    updatedAt: '2026-09-12T19:45:00Z',
  },
];

export const EnvVaultScreen: React.FC = () => {
  const [secrets, setSecrets] = useState<EnvSecret[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : INITIAL_SECRETS;
    } catch {
      return INITIAL_SECRETS;
    }
  });

  const [revealedIds, setRevealedIds] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDeptFilter, setSelectedDeptFilter] = useState('ALL');

  // Add / Edit Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formKey, setFormKey] = useState('');
  const [formValue, setFormValue] = useState('');
  const [formComment, setFormComment] = useState('');
  const [formDept, setFormDept] = useState('Engineering & Tech');

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(secrets));
    } catch (e) {
      console.warn('Failed to persist secrets vault:', e);
    }
  }, [secrets]);

  const toggleReveal = (id: string) => {
    setRevealedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const openAddModal = () => {
    setEditingId(null);
    setFormKey('');
    setFormValue('');
    setFormComment('');
    setFormDept('Engineering & Tech');
    setIsModalOpen(true);
  };

  const openEditModal = (secret: EnvSecret) => {
    setEditingId(secret.id);
    setFormKey(secret.key);
    setFormValue(secret.value);
    setFormComment(secret.comment);
    setFormDept(secret.department);
    setIsModalOpen(true);
  };

  const handleSaveSecret = (e: React.FormEvent) => {
    e.preventDefault();
    const formattedKey = formKey.trim().toUpperCase().replace(/\s+/g, '_');
    if (!formattedKey || !formValue.trim()) return;

    if (editingId) {
      // Update existing secret (Founder only)
      setSecrets((prev) =>
        prev.map((s) =>
          s.id === editingId
            ? {
                ...s,
                key: formattedKey,
                value: formValue.trim(),
                comment: formComment.trim() || 'No documentation provided.',
                department: formDept,
                updatedAt: new Date().toISOString(),
              }
            : s
        )
      );
    } else {
      // Create new secret
      const newSecret: EnvSecret = {
        id: `sec_${Date.now()}`,
        key: formattedKey,
        value: formValue.trim(),
        comment: formComment.trim() || 'No documentation provided.',
        department: formDept,
        updatedAt: new Date().toISOString(),
      };
      setSecrets((prev) => [newSecret, ...prev]);
    }

    setIsModalOpen(false);
  };

  const handleDeleteSecret = (id: string, keyName: string) => {
    if (window.confirm(`Are you sure you want to permanently delete secret ${keyName}? Autonomous agents using this variable will lose access.`)) {
      setSecrets((prev) => prev.filter((s) => s.id !== id));
    }
  };

  const filteredSecrets = secrets.filter((s) => {
    const matchesSearch =
      s.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.comment.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesDept =
      selectedDeptFilter === 'ALL' || s.department === selectedDeptFilter;
    return matchesSearch && matchesDept;
  });

  return (
    <div className="flex-1 flex flex-col bg-white text-[#0A0A0A] animate-screen-enter space-y-4 pb-[max(env(safe-area-inset-bottom),5rem)]">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-[#E6391E] font-bold tracking-widest uppercase">
              SECURITY & VAULT
            </span>
            <span className="font-mono text-[9px] px-1.5 py-0.2 bg-[#0A0A0A] text-white font-bold uppercase">
              .ENV RUNTIME
            </span>
          </div>

          <button
            onClick={openAddModal}
            className="flex items-center gap-1 font-mono text-[10px] font-bold bg-[#0A0A0A] text-white px-2.5 py-1 hover:bg-[#E6391E] transition-colors border border-[#0A0A0A]"
          >
            <Plus className="w-3 h-3" />
            <span>ADD SECRET</span>
          </button>
        </div>

        <h2 className="text-3xl font-headline font-bold mt-1 text-[#0A0A0A]">
          .env Secrets Vault
        </h2>
        <p className="font-mono text-[11px] text-zinc-500 mt-0.5">
          Founder secrets repository • Immutable & read-only to autonomous agents
        </p>
      </div>

      {/* Inline Add / Edit Secret Drawer */}
      {isModalOpen && (
        <div className="border-2 border-[#0A0A0A] p-4 bg-zinc-50 space-y-3 animate-screen-enter font-mono text-xs">
          <div className="flex items-center justify-between border-b border-[#0A0A0A] pb-2">
            <span className="font-bold text-[#E6391E] flex items-center gap-1.5 uppercase">
              <Lock className="w-3.5 h-3.5" />
              {editingId ? 'EDIT FOUNDER SECRET' : 'ADD NEW SECRET'}
            </span>
            <button
              onClick={() => setIsModalOpen(false)}
              className="text-zinc-500 hover:text-[#0A0A0A]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <form onSubmit={handleSaveSecret} className="space-y-3">
            <div>
              <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-1">
                Variable Name *
              </label>
              <input
                type="text"
                placeholder="e.g. STRIPE_SECRET_KEY"
                value={formKey}
                onChange={(e) => setFormKey(e.target.value)}
                required
                className="w-full bg-white border border-[#0A0A0A] p-2 text-xs font-mono text-[#0A0A0A] outline-none focus:border-[#E6391E]"
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-1">
                Secret Value *
              </label>
              <input
                type="text"
                placeholder="Paste token, API key, or connection URI..."
                value={formValue}
                onChange={(e) => setFormValue(e.target.value)}
                required
                className="w-full bg-white border border-[#0A0A0A] p-2 text-xs font-mono text-[#0A0A0A] outline-none focus:border-[#E6391E]"
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-1">
                Authorized Department
              </label>
              <select
                value={formDept}
                onChange={(e) => setFormDept(e.target.value)}
                className="w-full bg-white border border-[#0A0A0A] p-2 text-xs font-mono text-[#0A0A0A] outline-none focus:border-[#E6391E]"
              >
                <option value="Engineering & Tech">Engineering & Tech</option>
                <option value="Executive & Eva">Executive & Eva</option>
                <option value="All Departments">All Departments (Global)</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-1">
                Comment & Purpose (Instructions for Agents)
              </label>
              <textarea
                placeholder="State what this key is used for so AI agents understand its context and scope..."
                value={formComment}
                onChange={(e) => setFormComment(e.target.value)}
                rows={2}
                className="w-full bg-white border border-[#0A0A0A] p-2 text-xs font-sans text-[#0A0A0A] outline-none focus:border-[#E6391E]"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-200">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-3 py-1.5 border border-[#0A0A0A] bg-white text-[#0A0A0A] hover:bg-zinc-100"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 border border-[#0A0A0A] bg-[#E6391E] text-white font-bold hover:bg-red-700 flex items-center gap-1"
              >
                <Check className="w-3.5 h-3.5" />
                Save Secret
              </button>
            </div>
          </form>
        </div>
      )}

      {/* STRICT SECURITY INVARIANT BANNER */}
      <div className="border-2 border-[#0A0A0A] p-3.5 bg-zinc-50 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-[#E6391E]" />
            <span className="font-mono text-xs font-bold text-[#0A0A0A] tracking-wider uppercase">
              FOUNDER SECRETS GOVERNANCE
            </span>
          </div>
          <span className="font-mono text-[8px] font-bold px-1.5 py-0.5 bg-emerald-100 text-emerald-800 border border-emerald-300 uppercase">
            READ-ONLY TO AGENTS
          </span>
        </div>

        <p className="font-mono text-[10px] text-zinc-600 leading-relaxed">
          Only the Founder can <strong>create, edit, or delete</strong> secrets. All autonomous agents (Worker AGY-1, Research AGY-2, Reviewer Opus, Eva) have strictly verified <strong>READ-ONLY</strong> access to inject variables into isolated Git worktrees as needed. Agents cannot mutate or destroy keys.
        </p>
      </div>

      {/* Search & Department Filter Bar */}
      <div className="space-y-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder="Search variables by KEY or comment..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-white border border-[#0A0A0A] pl-8 pr-3 py-1.5 font-mono text-xs text-[#0A0A0A] outline-none focus:border-[#E6391E]"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 font-mono text-[10px]">
          {['ALL', 'Engineering & Tech', 'Executive & Eva', 'All Departments'].map((dept) => (
            <button
              key={dept}
              onClick={() => setSelectedDeptFilter(dept)}
              className={`px-2 py-0.5 border uppercase whitespace-nowrap transition-colors ${
                selectedDeptFilter === dept
                  ? 'bg-[#0A0A0A] text-white border-[#0A0A0A] font-bold'
                  : 'bg-white text-zinc-600 border-zinc-300 hover:border-[#0A0A0A]'
              }`}
            >
              {dept}
            </button>
          ))}
        </div>
      </div>

      {/* Secrets List */}
      <div className="space-y-3">
        {filteredSecrets.map((secret) => {
          const isRevealed = Boolean(revealedIds[secret.id]);
          const isCopied = copiedId === secret.id;

          return (
            <div
              key={secret.id}
              className="border border-[#0A0A0A] p-3.5 bg-white space-y-2.5"
            >
              {/* Top row: Key Name & Department Scope Badge */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <Key className="w-3.5 h-3.5 text-[#E6391E] shrink-0" />
                  <span className="font-mono text-xs font-bold text-[#0A0A0A] tracking-wider break-all">
                    {secret.key}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="font-mono text-[8px] font-bold px-1.5 py-0.5 border border-zinc-300 bg-zinc-100 text-zinc-700 uppercase">
                    {secret.department}
                  </span>

                  {/* Founder Controls: Edit & Delete */}
                  <button
                    onClick={() => openEditModal(secret)}
                    className="p-1 text-zinc-400 hover:text-[#0A0A0A] transition-colors"
                    title="Edit secret value/comment"
                  >
                    <Edit3 className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => handleDeleteSecret(secret.id, secret.key)}
                    className="p-1 text-zinc-400 hover:text-[#E6391E] transition-colors"
                    title="Delete secret"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>

              {/* Masked Secret Value Box */}
              <div className="flex items-center justify-between border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 font-mono text-xs">
                <span className="truncate mr-2 select-all text-zinc-800">
                  {isRevealed
                    ? secret.value
                    : '••••••••••••••••••••••••••••••••'}
                </span>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => toggleReveal(secret.id)}
                    className="text-zinc-500 hover:text-[#0A0A0A] transition-colors p-0.5"
                    title={isRevealed ? 'Hide secret' : 'Reveal secret'}
                  >
                    {isRevealed ? (
                      <EyeOff className="w-3.5 h-3.5 text-[#E6391E]" />
                    ) : (
                      <Eye className="w-3.5 h-3.5" />
                    )}
                  </button>

                  <button
                    onClick={() => handleCopy(secret.id, secret.value)}
                    className="text-zinc-500 hover:text-[#0A0A0A] transition-colors p-0.5"
                    title="Copy secret to clipboard"
                  >
                    {isCopied ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </div>

              {/* Founder Documentation & Purpose Comment */}
              <div className="space-y-1 pt-1 border-t border-zinc-100">
                <span className="font-mono text-[9px] text-zinc-400 font-bold uppercase block">
                  DEPARTMENT USAGE / PURPOSE:
                </span>
                <p className="font-sans text-xs text-zinc-600 leading-normal">
                  {secret.comment}
                </p>
              </div>

              {/* Timestamp footer */}
              <div className="flex items-center justify-between font-mono text-[9px] text-zinc-400 pt-1">
                <span>PERMISSION: READ-ONLY TO AGENTS</span>
                <span>SYNCED {new Date(secret.updatedAt).toLocaleDateString()}</span>
              </div>
            </div>
          );
        })}

        {filteredSecrets.length === 0 && (
          <div className="border border-dashed border-zinc-300 p-6 text-center text-zinc-400 font-mono text-xs">
            No secrets match query "{searchQuery}".
          </div>
        )}
      </div>
    </div>
  );
};
