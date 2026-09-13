// Locomotive Design Tokens & AlphaBrain Desktop Types

export const LOCOMOTIVE_TOKENS = {
  colors: {
    surface: '#FFFFFF',   // Pure white backgrounds — no grays, no off-whites
    onSurface: '#0A0A0A', // Pure black text — not #333, not #111
    primary: '#E6391E',   // Signature red-orange — accents, status dots, active states
    outline: '#0A0A0A',   // Structural borders — same as onSurface
  },
  typography: {
    headlineXL: {
      fontFamily: "'Space Grotesk', sans-serif",
      fontWeight: 700,
      letterSpacing: '-0.03em',
    },
    body: {
      fontFamily: "'Inter', sans-serif",
      fontWeight: 400,
    },
    mono: {
      fontFamily: "'Fira Code', monospace",
      fontWeight: 400,
    },
  },
  borders: {
    structural: '1px solid #0A0A0A',
  },
  borderRadius: {
    default: '0px', // Zero border-radius everywhere — brutalist, no rounding
  },
} as const;

export type ScreenId =
  | 'M01_NodeSetup'
  | 'M02_PairingStation'
  | 'M03_CommandNode'
  | 'M04_SecurityEnclave';

export interface DependencyReport {
  git_version: string;
  node_version: string;
  python_version: string;
  agy_version: string;
  all_satisfied: boolean;
  details: Record<string, string>;
}

export interface NodeRegistration {
  node_id: string;
  status: 'registered' | 'offline' | 'pending';
  backend_url: string;
  registered_at: string;
  cluster_name: string;
}

export interface QrPayloadV2 {
  v: 2;
  type: 'CLOUD_PROVISION';
  backend_url: string;
  session_token: string;
  node_id: string;
  node_ed25519_pubkey: string;
  issued_at: string;
  expires_at: string;
  sig: string;
  sas_code: string;
}

export interface TaskResult {
  task_id: string;
  status: 'completed' | 'failed' | 'error';
  exit_code: number;
  output: string;
  lease_id: string;
}

export interface SystemMetrics {
  cpu_usage: number;
  memory_used_mb: number;
  memory_total_mb: number;
  disk_used_gb: number;
  disk_total_gb: number;
  uptime_seconds: number;
  active_workers: number;
}

export interface ActiveTask {
  id: string;
  title: string;
  priority: 'P0' | 'P1' | 'P2';
  branch: string;
  status: 'running' | 'queued' | 'passed' | 'failed';
  duration: string;
}

export interface TerminalLog {
  id: string;
  timestamp: string;
  stream: 'stdout' | 'stderr' | 'system';
  text: string;
}

export interface TrustedDevice {
  id: string;
  name: string;
  platform: 'iOS' | 'Android' | 'Web' | 'CLI';
  sas_code: string;
  paired_at: string;
  status: 'active' | 'revoked';
}

export interface ApiVaultItem {
  id: string;
  name: string;
  key_alias: string;
  masked_value: string;
  last_used: string;
  in_keychain: boolean;
}
