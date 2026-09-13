import React, { useState } from 'react';
import { Lock, Key, Smartphone, ShieldCheck, AlertTriangle, Trash2, Eye, EyeOff, CheckCircle } from 'lucide-react';
import { ApiVaultItem, ScreenId, TrustedDevice } from '../types';

interface Props {
  onNavigate: (screen: ScreenId) => void;
}

export const M04_SecurityEnclave: React.FC<Props> = ({ onNavigate }) => {
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [isLocked, setIsLocked] = useState(false);

  const [vaultItems, setVaultItems] = useState<ApiVaultItem[]>([
    {
      id: '1',
      name: 'Claude Opus & Sonnet Key',
      key_alias: 'ANTHROPIC_API_KEY',
      masked_value: 'sk-ant-api03-9kL2...8f9a',
      last_used: '2 mins ago',
      in_keychain: true,
    },
    {
      id: '2',
      name: 'Gemini Pro Multi-Account Vault',
      key_alias: 'GEMINI_API_KEY',
      masked_value: 'AIzaSyD-8491...bc39',
      last_used: '15 mins ago',
      in_keychain: true,
    },
    {
      id: '3',
      name: 'OpenAI Enterprise Key',
      key_alias: 'OPENAI_API_KEY',
      masked_value: 'sk-proj-49201...99aa',
      last_used: '1 hour ago',
      in_keychain: true,
    },
    {
      id: '4',
      name: 'GitHub Deployment Token',
      key_alias: 'GITHUB_TOKEN',
      masked_value: 'ghp_48291048...7710',
      last_used: '3 hours ago',
      in_keychain: true,
    },
  ]);

  const [devices, setDevices] = useState<TrustedDevice[]>([
    {
      id: 'dev_iphone_16_pro',
      name: 'Founder iPhone 16 Pro Max',
      platform: 'iOS',
      sas_code: '8492',
      paired_at: '2026-09-13 12:15:00',
      status: 'active',
    },
    {
      id: 'dev_ipad_m4',
      name: 'Executive iPad Pro 13"',
      platform: 'iOS',
      sas_code: '3109',
      paired_at: '2026-09-11 09:30:00',
      status: 'active',
    },
  ]);

  const [agentPermissions, setAgentPermissions] = useState({
    worktreeIsolation: true,
    sandboxContainment: true,
    shellExecution: true,
    remoteGitPush: false,
  });

  const toggleShowKey = (id: string) => {
    setShowKeys((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleRevokeDevice = (deviceId: string) => {
    setDevices((devs) => devs.filter((d) => d.id !== deviceId));
  };

  const handleLockEnclave = () => {
    setIsLocked(true);
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8 bg-white text-[#0A0A0A] font-sans">
      {/* Header */}
      <div className="border-b border-[#0A0A0A] pb-4 flex justify-between items-end">
        <div>
          <span className="text-xs font-mono tracking-widest uppercase bg-[#0A0A0A] text-white px-2 py-0.5 font-bold">
            Screen M-04
          </span>
          <h1 className="text-3xl font-bold font-mono tracking-tight mt-2">
            SECURITY ENCLAVE & ACCESS VAULT
          </h1>
          <p className="text-sm text-neutral-600 mt-1">
            macOS Keychain hardware-backed API key storage, trusted mobile companions, and agent permissions.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleLockEnclave}
            className={`flex items-center gap-1.5 px-3 py-1.5 border border-[#0A0A0A] text-xs font-mono font-bold uppercase transition-colors ${
              isLocked ? 'bg-rose-600 text-white' : 'bg-neutral-100 hover:bg-rose-50 text-rose-800 border-rose-800'
            }`}
          >
            <Lock className="w-3.5 h-3.5" />
            <span>{isLocked ? 'ENCLAVE LOCKED' : 'Emergency Lock'}</span>
          </button>
        </div>
      </div>

      {/* Node Identity Banner */}
      <div className="border-2 border-[#0A0A0A] p-5 bg-neutral-50 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-600" />
            <span className="text-xs font-mono font-bold uppercase tracking-wider">
              Node Cryptographic Identity
            </span>
          </div>
          <div className="text-base font-bold font-mono">AB-MACBOOK-PRO-M4</div>
          <p className="text-xs font-mono text-neutral-600">
            Ed25519 Pubkey: <code className="bg-neutral-200 px-1 py-0.5 text-[11px]">MCowBQYDK2VwAyEA2r4F/AB9y9nJzZ1sH9E6x2T61bKk8V9q7f5d3a1b0c=</code>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right font-mono text-xs">
            <span className="text-neutral-500 block text-[10px] uppercase">Storage</span>
            <span className="font-bold text-emerald-800">macOS Keychain Protected</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Left Column: API Key Vault */}
        <div className="space-y-6">
          <div className="border border-[#0A0A0A] p-5 space-y-4">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-[#E6391E]" />
                <h2 className="text-sm font-mono font-bold uppercase tracking-wider">
                  macOS Keychain Secret Vault
                </h2>
              </div>
              <span className="text-[10px] font-mono bg-neutral-200 px-2 py-0.5 uppercase font-bold">
                {vaultItems.length} Keys
              </span>
            </div>

            <div className="space-y-3">
              {vaultItems.map((item) => (
                <div
                  key={item.id}
                  className="border border-neutral-300 p-3 bg-white space-y-1 font-mono text-xs"
                >
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-black">{item.name}</span>
                    <span className="text-[10px] text-emerald-700 font-bold flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" /> Keychain Verified
                    </span>
                  </div>
                  <div className="text-[11px] text-neutral-500">{item.key_alias}</div>
                  <div className="flex justify-between items-center pt-1">
                    <span className="text-neutral-800 font-mono bg-neutral-100 px-2 py-0.5 border border-neutral-200">
                      {showKeys[item.id] ? item.masked_value.replace('...', 'ABCDEF123456') : item.masked_value}
                    </span>
                    <button
                      onClick={() => toggleShowKey(item.id)}
                      className="p-1 hover:bg-neutral-100 text-neutral-600"
                    >
                      {showKeys[item.id] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Agent Permission Matrix */}
          <div className="border border-[#0A0A0A] p-5 space-y-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-[#E6391E]" />
              <h2 className="text-sm font-mono font-bold uppercase tracking-wider">
                Autonomous Agent Sandbox Boundaries
              </h2>
            </div>

            <div className="space-y-3 font-mono text-xs">
              {[
                {
                  label: 'Worktree Isolation',
                  desc: 'Agents execute solely in ephemeral task worktrees',
                  key: 'worktreeIsolation',
                  checked: agentPermissions.worktreeIsolation,
                },
                {
                  label: 'Sandbox Containment',
                  desc: 'Read/write scoped strictly to workspace target paths',
                  key: 'sandboxContainment',
                  checked: agentPermissions.sandboxContainment,
                },
                {
                  label: 'Subprocess Execution',
                  desc: 'Tauri plugin-shell daemon spawning permitted',
                  key: 'shellExecution',
                  checked: agentPermissions.shellExecution,
                },
                {
                  label: 'Remote Git Push Authority',
                  desc: 'Strictly manual operator push (disabled by default)',
                  key: 'remoteGitPush',
                  checked: agentPermissions.remoteGitPush,
                },
              ].map((perm) => (
                <div
                  key={perm.key}
                  className="flex items-center justify-between p-2.5 border border-neutral-200 bg-neutral-50"
                >
                  <div>
                    <div className="font-bold text-black">{perm.label}</div>
                    <div className="text-[10px] text-neutral-500">{perm.desc}</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={perm.checked}
                    onChange={(e) =>
                      setAgentPermissions((p) => ({ ...p, [perm.key]: e.target.checked }))
                    }
                    className="accent-[#E6391E] w-4 h-4 cursor-pointer"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Trusted Mobile Companions */}
        <div className="space-y-6">
          <div className="border border-[#0A0A0A] p-5 space-y-4">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-[#E6391E]" />
                <h2 className="text-sm font-mono font-bold uppercase tracking-wider">
                  Trusted Mobile Devices
                </h2>
              </div>
              <button
                onClick={() => onNavigate('M02_PairingStation')}
                className="px-2 py-1 border border-[#0A0A0A] text-xs font-mono uppercase font-semibold hover:bg-neutral-100"
              >
                + Pair Device
              </button>
            </div>

            <p className="text-xs text-neutral-500">
              Devices paired through Cloud Provisioning v2 QR code and Short Authentication String (SAS).
            </p>

            <div className="space-y-3">
              {devices.map((device) => (
                <div
                  key={device.id}
                  className="border border-[#0A0A0A] p-4 bg-white space-y-2 font-mono text-xs"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold text-black">{device.name}</div>
                      <div className="text-[11px] text-neutral-500">
                        Platform: {device.platform} • SAS: <strong className="text-[#E6391E]">{device.sas_code}</strong>
                      </div>
                    </div>
                    <button
                      onClick={() => handleRevokeDevice(device.id)}
                      className="p-1.5 text-neutral-500 hover:text-rose-600 hover:bg-rose-50"
                      title="Revoke Device Access"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="flex justify-between items-center text-[10px] text-neutral-400 border-t border-neutral-200 pt-2">
                    <span>Paired: {device.paired_at}</span>
                    <span className="text-emerald-700 font-bold uppercase">Authorized</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
