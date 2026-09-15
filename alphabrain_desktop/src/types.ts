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
  | 'M04_SecurityEnclave'
  | 'M05_MeetingSetup'
  | 'EvaMeeting'
  | 'Projects'
  | 'ModelRouter'
  | 'TriageQueue'
  | 'Departments'
  | 'EmergencyStop';

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

export interface EvaMeetingState {
  room_name: string;
  connected: boolean;
  participant_count: number;
  audio_active: boolean;
  video_active: boolean;
  eva_speaking: boolean;
  rtt_ms: number;
  packet_loss_percent: number;
}

export interface CommandNodeMetrics {
  cpu_usage: number;
  memory_used_mb: number;
  memory_total_mb: number;
  disk_used_gb: number;
  disk_total_gb: number;
  uptime_seconds: number;
  active_workers: number;
}

export interface CommandNodeTask {
  id: string;
  title: string;
  priority: string;
  branch: string;
  status: string;
  duration: string;
}

export interface CommandNodeLog {
  id: string;
  timestamp: string;
  stream: string;
  text: string;
}

export interface CommandNodeScreenData {
  node_id: string;
  hostname: string;
  cluster_name: string;
  status: string;
  metrics: CommandNodeMetrics;
  active_tasks: CommandNodeTask[];
  logs: CommandNodeLog[];
}

export interface SecurityEnclaveScreenData {
  node_key_fingerprint: string;
  is_locked: boolean;
  vault_items: ApiVaultItem[];
  devices: TrustedDevice[];
}

export interface MeetingSetupScreenData {
  room_name: string;
  participant_identity: string;
  livekit_url: string;
  token: string;
  audio_codec: string;
  sample_rate: number;
  audio_active: boolean;
  status: string;
}

export interface MeetingTokenResponse {
  room_name: string;
  token: string;
  expires_in_seconds: number;
}

export interface EmergencyStopState {
  active: boolean;
  locked_at: number | null;
  lock_file: string;
  reason: string;
  triggered_by: string;
}

export interface TaskSummary {
  task_id: string;
  title: string;
  category: string;
  status: string;
  priority: string;
  risk_class: string;
  created_at: number;
  updated_at: number;
  author: string;
  allowed_paths: string[];
  acceptance_commands: string[];
}

export interface TaskDetail extends TaskSummary {
  description: string;
  branch_name?: string;
  worktree_path?: string;
  review_notes?: string;
  gate_results: Record<string, any>;
  checkpoints: Array<{ step: string; status: string; timestamp?: number }>;
}

export interface ModelUtilityScore {
  account_name: string;
  email: string;
  tier: string;
  utility_score: number;
  weekly_quota_percent: number;
  five_hour_quota_percent: number;
  recommended_model: string;
}

export interface ProjectItem {
  name: string;
  path: string;
  mtime: number;
  is_active: boolean;
}
