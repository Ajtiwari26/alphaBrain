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
  | 'env_vault'
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
  | 'eva_meeting'
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
  video_active?: boolean;
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
  gemini_5h_percent?: number;
  gemini_weekly_percent?: number;
  gemini_5h_desc?: string;
  gemini_weekly_desc?: string;
  claude_5h_percent?: number;
  claude_weekly_percent?: number;
  claude_5h_desc?: string;
  claude_weekly_desc?: string;
  token_status?: string;
  is_active?: boolean;
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

// =====================================================================
// Amazon-Style Delivery Board Types
// =====================================================================

export interface DeliveryMilestone {
  id: string;
  step_number: number;
  title: string;
  status: 'completed' | 'in_transit' | 'pending';
  summary: string;
  timestamp_label: string;
  actor: string;
  checkpoint_badge: string;
}

export interface DeliveryMapResponse {
  project_id: string;
  project_name: string;
  overall_progress_percent: number;
  active_step: number;
  total_steps: number;
  stages: DeliveryMilestone[];
  inflight_task: {
    id?: string;
    title?: string;
    status?: string;
    branch?: string;
    worker?: string;
    elapsed_seconds?: number;
    required_reviewers?: string[];
  };
  metrics: {
    total_tasks_tracked?: number;
    merged_count?: number;
    active_worktrees?: number;
    safety_pass_rate?: number;
    current_git_head?: string;
  };
}

// =====================================================================
// Executive Architecture Reading Room Types
// =====================================================================

export interface ExecutiveDocSummary {
  doc_id: string;
  title: string;
  category: 'architecture' | 'senior_plan' | 'tech_stack' | 'meeting_spec';
  file_path: string;
  summary: string;
  word_count: number;
  last_modified: number;
  author: string;
}

export interface ExecutiveDocDetail {
  doc_id: string;
  title: string;
  category: string;
  file_path: string;
  content_markdown: string;
  sections: string[];
  last_modified: number;
  author: string;
}

// =====================================================================
// Client & Delegate Types (Admin Delegation)
// =====================================================================

export interface DelegateCredential {
  delegate_id: string;
  member_name: string;
  role: 'client_viewer' | 'team_delegate' | 'delegated_admin' | string;
  passcode: string;
  created_at: number;
  is_active: boolean;
  can_admin_verdict: boolean;
}

export interface DelegateInviteRequest {
  member_name: string;
  role?: string;
  notes?: string;
  grant_admin_access?: boolean;
}

export interface DelegateAuthResponse {
  authenticated: boolean;
  token: string;
  member_name: string;
  role: string;
  can_admin_verdict: boolean;
  message: string;
}

// =====================================================================
// Feedback, Problem Tickets & Admin Triage Handover
// =====================================================================

export interface FeedbackItem {
  id: string;
  project_id: string;
  author_name: string;
  author_role: string;
  problem_title: string;
  problem_description: string;
  created_at: number;
  status: 'pending_admin' | 'handed_over' | 'rejected' | 'resolved';
  eva_analysis?: string | null;
  eva_proposed_task?: Record<string, any> | null;
  admin_notes?: string | null;
  admitted_task_id?: string | null;
}

export interface FeedbackCreateRequest {
  author_name: string;
  author_role?: string;
  problem_title: string;
  problem_description: string;
}

export interface AdminFeedbackVerdictRequest {
  action: 'handover_pipeline' | 'dismiss_rejected' | 'resolve_direct';
  admin_notes?: string;
  reviewer_name?: string;
}

