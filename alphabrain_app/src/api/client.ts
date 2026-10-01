import {
  AuditLogEntry,
  DashboardScreenData,
  DeploymentTarget,
  EmergencyStopState,
  ExecutiveOverview,
  HardwareTelemetry,
  MeetingSetupScreenData,
  MeetingTokenResponse,
  ModelUtilityScore,
  PrivacyConsentStats,
  SelfHealingRadar,
  SprintFleetOverview,
  TaskDetail,
  TaskDiffResponse,
  TaskSummary,
  VoiceBriefing,
  DeliveryMapResponse,
  ExecutiveDocSummary,
  ExecutiveDocDetail,
  DelegateCredential,
  DelegateInviteRequest,
  DelegateAuthResponse,
  FeedbackItem,
  FeedbackCreateRequest,
  AdminFeedbackVerdictRequest,
} from '../types';

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const custom = localStorage.getItem('alpha_api_base');
    if (custom) return custom;
    // When running via Vite dev server proxy
    if (window.location.port === '5173') {
      return '/api/v1/mobile';
    }
  }
  return 'https://alpha-brain-staging.onrender.com/api/v1/mobile';
}

export function getAuthToken(): string {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('alpha_api_token') || 'ced2a32dd9a568fa22e606fa48381543';
  }
  return 'ced2a32dd9a568fa22e606fa48381543';
}

async function safeFetch<T = any>(endpoint: string, options?: RequestInit): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const token = getAuthToken();
  const res = await fetch(`${baseUrl}${endpoint}`, {
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
}

export const mobileApi = {
  getIncomingCall: async (): Promise<{ active_call: any | null }> => {
    return safeFetch('/voice/incoming');
  },
  respondIncomingCall: async (callId: string, action: 'accept' | 'decline'): Promise<any> => {
    return safeFetch(`/voice/incoming/${callId}/respond`, {
      method: 'POST',
      body: JSON.stringify({ action })
    });
  },
  triggerSimulatedCall: async (data?: any): Promise<any> => {
    return safeFetch('/voice/call/trigger', {
      method: 'POST',
      body: JSON.stringify(data || {})
    });
  },

  getOverview: (): Promise<ExecutiveOverview> =>
    safeFetch('/overview'),

  getDashboard: (): Promise<DashboardScreenData> =>
    safeFetch('/dashboard'),

  getMeetingSetup: (room = 'alphabrain-executive-briefing'): Promise<MeetingSetupScreenData> =>
    safeFetch(`/meet/setup?room=${encodeURIComponent(room)}`),

  getMeetingToken: (room = 'alphabrain-executive-briefing'): Promise<MeetingTokenResponse> =>
    safeFetch(`/meet/token?room=${encodeURIComponent(room)}`),

  listTriage: async (status?: string): Promise<TaskSummary[]> => {
    try {
      return await safeFetch(status ? `/triage?status=${status}` : '/triage');
    } catch (e) {
      console.warn('Failed to list triage tasks:', e);
      return [];
    }
  },

  reviewTask: (taskId: string, action: 'approve' | 'reject', notes: string) =>
    safeFetch(`/triage/${taskId}/review`, {
      method: 'POST',
      body: JSON.stringify({ action, founder_notes: notes }),
    }),

  getTaskDetail: (taskId: string): Promise<TaskDetail> =>
    safeFetch(`/tasks/${taskId}`),

  getTaskDiff: (taskId: string): Promise<TaskDiffResponse> =>
    safeFetch(`/tasks/${taskId}/diff`),

  promoteTask: (taskId: string) =>
    safeFetch(`/tasks/${taskId}/promote`, { method: 'POST' }),

  getVoiceBriefing: (): Promise<VoiceBriefing> =>
    safeFetch('/voice/briefing'),

  sendSpokenCommand: (commandText: string) =>
    safeFetch('/voice/command', {
      method: 'POST',
      body: JSON.stringify({ command_text: commandText }),
    }),

  getSprintFleet: (): Promise<SprintFleetOverview> =>
    safeFetch('/sprint'),

  getDeployments: async (): Promise<DeploymentTarget[]> => {
    try {
      return await safeFetch('/deployments');
    } catch (e) {
      console.warn('Failed to get deployments:', e);
      return [];
    }
  },

  triggerRollback: (deploymentId: string) =>
    safeFetch(`/deployments/${deploymentId}/rollback`, { method: 'POST' }),

  getSelfHealing: (): Promise<SelfHealingRadar> =>
    safeFetch('/self-healing'),

  getTelemetry: (): Promise<HardwareTelemetry> =>
    safeFetch('/telemetry'),

  getPrivacyStats: (): Promise<PrivacyConsentStats> =>
    safeFetch('/privacy'),

  purgePrivacy: () => safeFetch('/privacy/purge', { method: 'POST' }),

  getModelScores: async (): Promise<ModelUtilityScore[]> => {
    try {
      return await safeFetch('/models');
    } catch (e) {
      console.warn('Failed to fetch model utility scores:', e);
      return [];
    }
  },

  getAuditTrail: async (limit = 20): Promise<AuditLogEntry[]> => {
    try {
      return await safeFetch(`/audit?limit=${limit}`);
    } catch (e) {
      console.warn('Failed to fetch audit trail:', e);
      return [];
    }
  },

  getEmergencyStop: (): Promise<EmergencyStopState> =>
    safeFetch('/emergency-stop'),

  toggleEmergencyStop: (enable: boolean, reason: string): Promise<EmergencyStopState> =>
    safeFetch('/emergency-stop', {
      method: 'POST',
      body: JSON.stringify({ enable_stop: enable, reason }),
    }),

  getWorktrees: async (): Promise<Array<{ path: string; name: string; commit: string; branch: string }>> => {
    try {
      return await safeFetch('/worktrees');
    } catch (e) {
      console.warn('Failed to fetch git worktrees:', e);
      return [];
    }
  },

  getProjects: async (): Promise<Array<{ name: string; path: string; mtime: number; is_active: boolean }>> => {
    try {
      return await safeFetch('/projects');
    } catch (e) {
      console.warn('Failed to fetch project repositories:', e);
      return [];
    }
  },

  getEvaMeetingToken: async (
    room: string,
    identity = 'Ajay (Founder)',
    token?: string
  ): Promise<{ token: string; room_name?: string }> => {
    const rootBase = getApiBaseUrl().replace('/api/v1/mobile', '');
    const authToken = token || getAuthToken();
    try {
      const res = await fetch(`${rootBase}/api/meet/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({ room_name: room, identity }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Local fallback
    }
    return { token: 'simulated_webrtc_token', room_name: room };
  },

  createMeetingInvite: async (
    room: string,
    identity = 'Client',
    token?: string
  ): Promise<{ invite_token: string; invite_url: string }> => {
    const rootBase = getApiBaseUrl().replace('/api/v1/mobile', '');
    const authToken = token || getAuthToken();
    try {
      const res = await fetch(`${rootBase}/api/meet/invite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({ room_name: room, identity }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Local fallback
    }
    return {
      invite_token: 'client_invite_token',
      invite_url: `/meet#invite=${encodeURIComponent(room)}`,
    };
  },

  // =========================================================================
  // Amazon-Style Delivery Board
  // =========================================================================
  getDeliveryMap: async (projectId = 'alphabrain_dogfood'): Promise<DeliveryMapResponse> => {
    return safeFetch<DeliveryMapResponse>(`/delivery-map?project_id=${encodeURIComponent(projectId)}`);
  },

  // =========================================================================
  // Executive Architecture Reading Room
  // =========================================================================
  listExecutiveDocs: async (): Promise<ExecutiveDocSummary[]> => {
    return safeFetch<ExecutiveDocSummary[]>('/docs/index');
  },

  getExecutiveDoc: async (docId: string): Promise<ExecutiveDocDetail> => {
    return safeFetch<ExecutiveDocDetail>(`/docs/${encodeURIComponent(docId)}`);
  },

  // =========================================================================
  // Delegates & Access Control
  // =========================================================================
  listDelegates: async (): Promise<DelegateCredential[]> => {
    return safeFetch<DelegateCredential[]>('/delegates/list');
  },

  createDelegateInvite: async (req: DelegateInviteRequest): Promise<DelegateCredential> => {
    return safeFetch<DelegateCredential>('/delegates/invite', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  authenticateDelegate: async (req: { delegate_id: string; passcode: string }): Promise<DelegateAuthResponse> => {
    return safeFetch<DelegateAuthResponse>('/delegates/auth', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  // =========================================================================
  // Problem Tickets, Opinions & Admin Handover
  // =========================================================================
  listFeedback: async (projectId = 'alphabrain_dogfood'): Promise<FeedbackItem[]> => {
    return safeFetch<FeedbackItem[]>(`/feedback?project_id=${encodeURIComponent(projectId)}`);
  },

  submitFeedback: async (req: FeedbackCreateRequest, projectId = 'alphabrain_dogfood'): Promise<FeedbackItem> => {
    return safeFetch<FeedbackItem>(`/feedback?project_id=${encodeURIComponent(projectId)}`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  adminVerdictOnFeedback: async (
    feedbackId: string,
    verdict: AdminFeedbackVerdictRequest
  ): Promise<FeedbackItem> => {
    return safeFetch<FeedbackItem>(`/feedback/${encodeURIComponent(feedbackId)}/admin-verdict`, {
      method: 'POST',
      body: JSON.stringify(verdict),
    });
  },
};

