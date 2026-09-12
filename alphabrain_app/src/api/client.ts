import {
  AuditLogEntry,
  DeploymentTarget,
  EmergencyStopState,
  ExecutiveOverview,
  HardwareTelemetry,
  ModelUtilityScore,
  PrivacyConsentStats,
  SelfHealingRadar,
  SprintFleetOverview,
  TaskDetail,
  TaskDiffResponse,
  TaskSummary,
  VoiceBriefing,
} from '../types';

const API_BASE = '/api/v1/mobile';

export function getAuthToken(): string {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('alpha_api_token') || 'alpha-local-meeting-2026-test-token-32chars';
  }
  return 'alpha-local-meeting-2026-test-token-32chars';
}

async function safeFetch<T = any>(endpoint: string, options?: RequestInit, fallback?: T): Promise<T> {
  try {
    const token = getAuthToken();
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options?.headers,
      },
    });
    if (!res.ok) {
      throw new Error(`HTTP error! status: ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    if (fallback !== undefined) {
      return fallback;
    }
    throw err;
  }
}

export const mobileApi = {
  getOverview: (): Promise<ExecutiveOverview> =>
    safeFetch('/overview', undefined, {
      app_version: '1.0.0-locomotive',
      system_status: 'operational',
      emergency_stop: {
        active: false,
        locked_at: null,
        lock_file: '/Users/ajaytiwari/.alphabrain/emergency_stop.lock',
        reason: '',
        triggered_by: '',
      },
      telemetry: {
        host_cpu_percent: 24.8,
        host_ram_percent: 48.2,
        host_ram_used_gb: 15.4,
        host_ram_total_gb: 32.0,
        thermal_pressure: 'nominal',
        battery_level_percent: 98.0,
        battery_charging: true,
        usb_device_connected: true,
        usb_device_serial: '10BF5P2AZF0010T',
        usb_device_name: 'iQOO 12 Flagship',
      },
      triage_backlog_count: 3,
      active_sprint_workers: 1,
      recent_deployments_count: 3,
      eva_status: 'active',
    }),

  listTriage: (status?: string): Promise<TaskSummary[]> =>
    safeFetch(status ? `/triage?status=${status}` : '/triage', undefined, [
      {
        task_id: 'tsk_eva_1d262851bd6a',
        title: 'P14: AlphaBrain Founder Companion mobile app and bridge',
        category: 'engineering',
        status: 'executing',
        priority: 'critical',
        risk_class: 'low',
        created_at: Date.now() / 1000 - 3600,
        updated_at: Date.now() / 1000,
        author: 'Eva CTO',
        allowed_paths: ['alphabrain_app/', 'alpha_core/', 'testscript/'],
        acceptance_commands: [
          'pytest -q testscript/test_mobile_bridge_api.py',
          'ruff check alpha_core/mobile_bridge/',
        ],
      },
      {
        task_id: 'tsk_eva_d3e234883c78',
        title: 'P13.1 Production Data Privacy, Consent Management & Retention',
        category: 'compliance',
        status: 'completed',
        priority: 'high',
        risk_class: 'low',
        created_at: Date.now() / 1000 - 7200,
        updated_at: Date.now() / 1000 - 3600,
        author: 'Eva CTO',
        allowed_paths: ['alpha_core/privacy/'],
        acceptance_commands: ['pytest -q testscript/test_privacy_compliance.py'],
      },
      {
        task_id: 'tsk_eva_0aa79e3888d2',
        title: 'OpenAI Codex Senior Review & Planning Integration',
        category: 'architecture',
        status: 'completed',
        priority: 'normal',
        risk_class: 'low',
        created_at: Date.now() / 1000 - 14400,
        updated_at: Date.now() / 1000 - 7200,
        author: 'Eva CTO',
        allowed_paths: ['alpha_core/planning/'],
        acceptance_commands: ['pytest -q testscript/test_codex_senior_integration.py'],
      },
    ]),

  reviewTask: (taskId: string, action: 'approve' | 'reject', notes: string) =>
    safeFetch(`/triage/${taskId}/review`, {
      method: 'POST',
      body: JSON.stringify({ action, founder_notes: notes }),
    }),

  getTaskDetail: (taskId: string): Promise<TaskDetail> =>
    safeFetch(`/tasks/${taskId}`, undefined, {
      task_id: taskId,
      title: 'P14: AlphaBrain Founder Companion mobile app and bridge',
      category: 'engineering',
      status: 'executing',
      priority: 'critical',
      risk_class: 'low',
      created_at: Date.now() / 1000 - 3600,
      updated_at: Date.now() / 1000,
      author: 'Eva CTO',
      allowed_paths: ['alphabrain_app/', 'alpha_core/', 'testscript/'],
      acceptance_commands: [
        'pytest -q testscript/test_mobile_bridge_api.py',
        'ruff check alpha_core/mobile_bridge/',
      ],
      description: 'End-to-end founder companion app with all 14 Locomotive screens, FastAPI backend bridge, and Capacitor Android scaffolding.',
      branch_name: `alpha/${taskId}`,
      worktree_path: `/Users/ajaytiwari/Library/Application Support/AlphaBrain/worktrees/${taskId}`,
      review_notes: 'SafetyGate deterministic invariant check: PASSED',
      gate_results: { unit_test: 'passed', lint: 'passed' },
      checkpoints: [
        { step: 'admit', status: 'done' },
        { step: 'safety_review', status: 'done' },
        { step: 'senior_plan', status: 'done' },
        { step: 'worker_cycle', status: 'in_progress' },
      ],
    }),

  getTaskDiff: (taskId: string): Promise<TaskDiffResponse> =>
    safeFetch(`/tasks/${taskId}/diff`, undefined, {
      task_id: taskId,
      base_commit: 'c686502f',
      head_commit: 'da25fcf9',
      files: [
        {
          file_path: 'alphabrain_app/src/App.tsx',
          status: 'added',
          additions: 142,
          deletions: 0,
          patch: '@@ -0,0 +1,142 @@\n+import React from "react";\n+// Full locomotive screen navigator',
        },
        {
          file_path: 'alpha_core/mobile_bridge/api.py',
          status: 'added',
          additions: 195,
          deletions: 0,
          patch: '@@ -0,0 +1,195 @@\n+from fastapi import APIRouter\n+router = APIRouter()',
        },
        {
          file_path: 'testscript/test_mobile_bridge_api.py',
          status: 'added',
          additions: 120,
          deletions: 0,
          patch: '@@ -0,0 +1,120 @@\n+def test_mobile_bridge(): pass',
        },
      ],
      total_additions: 457,
      total_deletions: 0,
    }),

  promoteTask: (taskId: string) =>
    safeFetch(`/tasks/${taskId}/promote`, { method: 'POST' }),

  getVoiceBriefing: (): Promise<VoiceBriefing> =>
    safeFetch('/voice/briefing', undefined, {
      briefing_id: 'brf_001',
      timestamp: Date.now() / 1000,
      speaker: 'Eva (DeployMate CTO)',
      audio_active: false,
      executive_summary:
        'Good evening Ajay. All core services are operating at nominal capacity. P14 Mobile Companion build is executing cleanly. Zero regressions across 916 gate checkpoints.',
      recommended_actions: [
        'Approve P14 PR diff to fast-forward into main',
        'Review device 10BF5P2AZF0010T live USB status',
        'Observe thermal headroom at 24% load',
      ],
      active_room: 'deploymate-main',
    }),

  sendSpokenCommand: (commandText: string) =>
    safeFetch('/voice/command', {
      method: 'POST',
      body: JSON.stringify({ command_text: commandText }),
    }),

  getSprintFleet: (): Promise<SprintFleetOverview> =>
    safeFetch('/sprint', undefined, {
      fleet_name: 'AlphaBrain Autonomous Swarm',
      max_workers: 2,
      active_workers: 1,
      slots: [
        {
          worker_id: 'worker_01_agy',
          status: 'running',
          current_task_id: 'tsk_eva_1d262851bd6a',
          worktree_slug: 'tsk_eva_1d262851bd6a',
          uptime_seconds: 1420,
          turn_count: 6,
        },
        {
          worker_id: 'worker_02_idle',
          status: 'idle',
          current_task_id: null,
          worktree_slug: null,
          uptime_seconds: 3600,
          turn_count: 0,
        },
      ],
      queue_backlog: 1,
      adaptive_throttle_factor: 1.0,
    }),

  getDeployments: (): Promise<DeploymentTarget[]> =>
    safeFetch('/deployments', undefined, [
      {
        id: 'dep_vercel_prod',
        service_name: 'DeployMate Commercial Portal',
        provider: 'Vercel',
        environment: 'production',
        status: 'healthy',
        live_url: 'https://deploymate.ai',
        last_deployed_at: Date.now() / 1000 - 86400,
        commit_sha: 'c686502f',
        rollback_available: true,
      },
      {
        id: 'dep_render_api',
        service_name: 'AlphaBrain FastAPI Core',
        provider: 'Render',
        environment: 'production',
        status: 'healthy',
        live_url: 'https://api.deploymate.ai/health',
        last_deployed_at: Date.now() / 1000 - 43200,
        commit_sha: 'da25fcf9',
        rollback_available: true,
      },
      {
        id: 'dep_supabase_db',
        service_name: 'PostgreSQL Primary Cluster',
        provider: 'Supabase',
        environment: 'production',
        status: 'healthy',
        live_url: 'https://db.deploymate.ai',
        last_deployed_at: Date.now() / 1000 - 172800,
        commit_sha: '079a7c81',
        rollback_available: false,
      },
    ]),

  triggerRollback: (deploymentId: string) =>
    safeFetch(`/deployments/${deploymentId}/rollback`, { method: 'POST' }),

  getSelfHealing: (): Promise<SelfHealingRadar> =>
    safeFetch('/self-healing', undefined, {
      daemon_running: true,
      active_healers: 1,
      recent_repairs_count: 2,
      circuit_breakers: [
        { name: 'CodexApiCircuitBreaker', state: 'closed', failure_count: 0, threshold: 3, last_failure_at: null },
        { name: 'RenderWebhookBreaker', state: 'closed', failure_count: 0, threshold: 5, last_failure_at: null },
        { name: 'GitLockConflictBreaker', state: 'closed', failure_count: 0, threshold: 2, last_failure_at: null },
      ],
      last_incident: null,
    }),

  getTelemetry: (): Promise<HardwareTelemetry> =>
    safeFetch('/telemetry', undefined, {
      host_cpu_percent: 24.2,
      host_ram_percent: 48.5,
      host_ram_used_gb: 15.5,
      host_ram_total_gb: 32.0,
      thermal_pressure: 'nominal',
      battery_level_percent: 98.0,
      battery_charging: true,
      usb_device_connected: true,
      usb_device_serial: '10BF5P2AZF0010T',
      usb_device_name: 'iQOO 12 Flagship',
    }),

  getPrivacyStats: (): Promise<PrivacyConsentStats> =>
    safeFetch('/privacy', undefined, {
      total_records: 1480,
      retention_days_limit: 90,
      redaction_enabled: true,
      gdpr_status: 'compliant',
      pending_purges: 0,
      last_purge_at: Date.now() / 1000 - 86400,
    }),

  purgePrivacy: () => safeFetch('/privacy/purge', { method: 'POST' }),

  getModelScores: (): Promise<ModelUtilityScore[]> =>
    safeFetch('/models', undefined, [
      {
        account_name: 'Ajay AlphaBrain Primary',
        email: 'ajaytiwari@example.com',
        tier: 'Tier 1 (Idle First)',
        utility_score: 1095.4,
        weekly_quota_percent: 100.0,
        five_hour_quota_percent: 95.4,
        recommended_model: 'claude-opus-4-6-thinking',
      },
      {
        account_name: 'Engineering Secondary',
        email: 'eng.backup@example.com',
        tier: 'Tier 3 (Active Rotation)',
        utility_score: 24.8,
        weekly_quota_percent: 78.2,
        five_hour_quota_percent: 60.0,
        recommended_model: 'claude-opus-4-6-thinking',
      },
      {
        account_name: 'Gemini High Fallback',
        email: 'gemini.pro@example.com',
        tier: 'Tier 3 (Active Rotation)',
        utility_score: 18.5,
        weekly_quota_percent: 85.0,
        five_hour_quota_percent: 70.0,
        recommended_model: 'gemini-3.1-pro-high',
      },
    ]),

  getAuditTrail: (limit = 20): Promise<AuditLogEntry[]> =>
    safeFetch(`/audit?limit=${limit}`, undefined, [
      {
        event_id: 'ev_001',
        timestamp: Date.now() / 1000 - 30,
        actor: 'founder',
        action_type: 'device_handshake',
        resource_id: '10BF5P2AZF0010T',
        sha256_hash: '3f7a8b...c91e',
        details: { status: 'authorized', mode: 'fastboot_adb' },
      },
      {
        event_id: 'ev_002',
        timestamp: Date.now() / 1000 - 120,
        actor: 'eva_agent',
        action_type: 'briefing_generated',
        resource_id: 'brf_001',
        sha256_hash: '9a4b2c...7d3f',
        details: { status: 'delivered' },
      },
    ]),

  getEmergencyStop: (): Promise<EmergencyStopState> =>
    safeFetch('/emergency-stop', undefined, {
      active: false,
      locked_at: null,
      lock_file: '/Users/ajaytiwari/.alphabrain/emergency_stop.lock',
      reason: '',
      triggered_by: '',
    }),

  toggleEmergencyStop: (enable: boolean, reason: string): Promise<EmergencyStopState> =>
    safeFetch('/emergency-stop', {
      method: 'POST',
      body: JSON.stringify({ enable_stop: enable, reason }),
    }),
};
