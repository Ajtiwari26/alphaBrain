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
  | 'task_detail'
  | 'code_diff'
  | 'voice_briefing'
  | 'sprint_fleet'
  | 'pr_promotion'
  | 'hardware_telemetry'
  | 'self_healing'
  | 'privacy_compliance'
  | 'audit_trail'
  | 'emergency_stop';

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

export interface DiffFile {
  file_path: string;
  status: string;
  additions: number;
  deletions: number;
  patch: string;
}

export interface TaskDiffResponse {
  task_id: string;
  base_commit: string;
  head_commit: string;
  files: DiffFile[];
  total_additions: number;
  total_deletions: number;
}

export interface VoiceBriefing {
  briefing_id: string;
  timestamp: number;
  speaker: string;
  audio_active: boolean;
  executive_summary: string;
  recommended_actions: string[];
  active_room: string;
}

export interface WorkerSlot {
  worker_id: string;
  status: string;
  current_task_id: string | null;
  worktree_slug: string | null;
  uptime_seconds: number;
  turn_count: number;
}

export interface SprintFleetOverview {
  fleet_name: string;
  max_workers: number;
  active_workers: number;
  slots: WorkerSlot[];
  queue_backlog: number;
  adaptive_throttle_factor: number;
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

export interface CircuitBreakerStatus {
  name: string;
  state: string;
  failure_count: number;
  threshold: number;
  last_failure_at: number | null;
}

export interface SelfHealingRadar {
  daemon_running: boolean;
  active_healers: number;
  recent_repairs_count: number;
  circuit_breakers: CircuitBreakerStatus[];
  last_incident: string | null;
}

export interface PrivacyConsentStats {
  total_records: number;
  retention_days_limit: number;
  redaction_enabled: boolean;
  gdpr_status: string;
  pending_purges: number;
  last_purge_at: number | null;
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
