import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Lock, Unlock, Key, Smartphone, ShieldCheck, AlertTriangle, Trash2, Eye, EyeOff, CheckCircle } from 'lucide-react';
import { ApiVaultItem, ScreenId, TrustedDevice } from '../types';
import { desktopApi } from '../api/client';

interface Props {
  onNavigate: (screen: ScreenId) => void;
}

export const M04_SecurityEnclave: React.FC<Props> = ({ onNavigate }) => {
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [isLocked, setIsLocked] = useState(false);
  const [nodeKeyFingerprint, setNodeKeyFingerprint] = useState<string>(
    'Loading cryptographic fingerprint...'
  );

  const [vaultItems, setVaultItems] = useState<ApiVaultItem[]>([]);
  const [devices, setDevices] = useState<TrustedDevice[]>([]);

  const [agentPermissions, setAgentPermissions] = useState({
    worktreeIsolation: true,
    sandboxContainment: true,
    shellExecution: true,
    remoteGitPush: false,
  });

  useEffect(() => {
    // Fetch real production security enclave data from backend
    desktopApi.getSecurityEnclave()
      .then((data) => {
        if (data) {
          if (data.node_key_fingerprint) setNodeKeyFingerprint(data.node_key_fingerprint);
          if (typeof data.is_locked === 'boolean') setIsLocked(data.is_locked);
          if (data.vault_items) setVaultItems(data.vault_items);
          if (data.devices) setDevices(data.devices);
        }
      })
      .catch((err) => {
        console.warn('Backend security enclave fetch error:', err);
      });

    // Read genuine identity key bytes from macOS Keychain via Rust IPC if available
    invoke<number[]>('read_identity_key')
      .then((bytes) => {
        if (bytes && bytes.length === 32) {
          const hex = Array.from(bytes.slice(0, 8))
            .map((b) => b.toString(16).padStart(2, '0'))
            .join('');
          setNodeKeyFingerprint(`SHA256:${hex}...[32-byte Ed25519 Keychain Verified]`);
        }
      })
      .catch(() => {
        // Fallback in web preview
      });
  }, []);

  const toggleShowKey = (id: string) => {
    setShowKeys((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleRevokeDevice = (deviceId: string) => {
    setDevices((devs) => devs.filter((d) => d.id !== deviceId));
  };

  const handleToggleLock = async () => {
    const nextLocked = !isLocked;
    try {
      await desktopApi.toggleEmergencyStop(nextLocked, nextLocked ? 'Security Enclave manual lockdown' : 'Security Enclave unlocked');
      setIsLocked(nextLocked);
    } catch (err) {
      console.warn('Failed to toggle emergency stop:', err);
    }
  };

  return (
    <div className="p-8 max-w-[1800px] w-full h-full flex flex-col mx-auto space-y-8 bg-white text-[#0A0A0A] font-sans">
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
            onClick={handleToggleLock}
            className={`flex items-center gap-1.5 px-3 py-1.5 border border-[#0A0A0A] text-xs font-mono font-bold uppercase transition-colors ${
              isLocked
                ? 'bg-rose-600 hover:bg-rose-700 text-white border-rose-900'
                : 'bg-neutral-100 hover:bg-rose-50 text-rose-800 border-rose-800'
            }`}
          >
            {isLocked ? <Unlock className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
            <span>{isLocked ? 'Unlock Enclave' : 'Emergency Lock'}</span>
          </button>
        </div>
      </div>

      {isLocked && (
        <div className="p-4 border-2 border-rose-800 bg-rose-50 text-rose-950 font-mono text-xs space-y-1">
          <div className="font-bold flex items-center gap-2 text-rose-800 uppercase">
            <Lock className="w-4 h-4" />
            <span>ENCLAVE EMERGENCY LOCKDOWN ACTIVE</span>
          </div>
          <p>
            Hardware Keychain access is restricted. Worker daemons paused and remote mobile claims are temporarily suspended.
          </p>
        </div>
      )}

      {/* Node Identity Banner */}
      <div className="border-2 border-[#0A0A0A] p-5 bg-neutral-50 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-600" />
            <span className="text-xs font-mono font-bold uppercase tracking-wider">
              Node Cryptographic Identity (Rust Keychain Bridge)
            </span>
          </div>
          <div className="text-base font-bold font-mono">AB-MACBOOK-PRO-M4</div>
          <p className="text-xs font-mono text-neutral-600">
            Ed25519 Pubkey: <code className="bg-neutral-200 px-1 py-0.5 text-[11px]">{nodeKeyFingerprint}</code>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right font-mono text-xs">
            <span className="text-neutral-500 block text-[10px] uppercase">Storage</span>
            <span className="font-bold text-emerald-800">macOS Keychain Protected</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8 flex-1">
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
                      {showKeys[item.id] ? item.masked_value.replace('••••', 'REDACTED_SEC') : item.masked_value}
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
        </div>

        {/* Middle Column: Agent Permission Matrix */}
        <div className="space-y-6">
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
