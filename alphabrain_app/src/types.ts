/**
 * Types mirroring AlphaBrain Mobile Bridge API (FastAPI)
 */

export type ScreenId =
  | 'splash'
  | 'auth'
  | 'instance_sync'
  | 'overview'
  | 'model_router'
  | 'departments'
  | 'agent_comms'
  | 'tech_dept'
  | 'worktrees'
  | 'triage'
  | 'live_stream'
  | 'deployments'
  | 'projects'
  | 'settings'
  | 'enrollment'
  | 'qr_provisioning'
  | 'sas_verification'
  | 'eva_meeting';


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

export interface ProvisioningPayload {
  device_serial: string;
  tunnel_port: number;
  daemon_version: string;
  sas_token: string;
  status: 'scanning' | 'verifying' | 'paired';
}

/**
 * Computes a salted SHA-256 cryptographic hash of a PIN string.
 */
export async function hashPin(pin: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(`alphabrain_pin_salt_${pin}`);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

export interface HardwareTelemetry {
  host_cpu_percent: number;
  host_ram_percent: number;
  host_ram_used_gb: number;
  host_ram_total_gb: number;
  thermal_pressure: string;
  battery_level_percent: number;
  battery_charging: boolean;
  usb_device_connected: boolean;
  usb_device_serial: string;
  usb_device_name: string;
}

export interface EmergencyStopState {
  active: boolean;
  locked_at: number | null;
  lock_file: string;
  reason: string;
  triggered_by: string;
}

export interface ExecutiveOverview {
  app_version: string;
  system_status: string;
  emergency_stop: EmergencyStopState;
  telemetry: HardwareTelemetry;
  triage_backlog_count: number;
  active_sprint_workers: number;
  recent_deployments_count: number;
  eva_status: string;
}

export interface DashboardScreenData {
  system_status: string;
  emergency_stop: EmergencyStopState;
  telemetry: HardwareTelemetry;
  hardware_sync_serial: string;
  ai_quotas_summary: string;
  ai_quotas_percent: number;
  active_projects_count: number;
  tech_dept_agents_count: number;
  triage_pending_count: number;
  worktrees_count: number;
  worktrees_summary: string;
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

export interface DeploymentTarget {
  id: string;
  service_name: string;
  provider: string;
  environment: string;
  status: string;
  live_url: string;
  last_deployed_at: number;
  commit_sha: string;
  rollback_available: boolean;
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

export interface AuditLogEntry {
  event_id: string;
  timestamp: number;
  actor: string;
  action_type: string;
  resource_id: string;
  sha256_hash: string;
  details: Record<string, any>;
}
