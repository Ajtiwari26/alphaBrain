import {
  CommandNodeScreenData,
  EmergencyStopState,
  MeetingSetupScreenData,
  MeetingTokenResponse,
  ModelUtilityScore,
  ProjectItem,
  SecurityEnclaveScreenData,
  TaskDetail,
  TaskSummary,
} from '../types';

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const custom = localStorage.getItem('alpha_api_base');
    if (custom) return custom;
    if (
      window.location.port === '5173' ||
      window.location.port === '1420'
    ) {
      return '/api/v1/mobile';
    }
  }
  return 'https://alpha-brain-staging.onrender.com/api/v1/mobile';
}

export async function getAuthToken(): Promise<string> {
  if (typeof window !== 'undefined') {
    try {
      if ((window as any).__TAURI_INTERNALS__) {
        const { invoke } = await import('@tauri-apps/api/core');
        const key = await invoke<string>('read_identity_key');
        if (key) return key;
      }
    } catch {
      // Non-tauri or keychain fallback
    }
    return sessionStorage.getItem('alpha_api_token') || localStorage.getItem('alpha_api_token') || 'ced2a32dd9a568fa22e606fa48381543';
  }
  return 'ced2a32dd9a568fa22e606fa48381543';
}

async function safeFetch<T = any>(endpoint: string, options?: RequestInit, timeoutMs = 8000): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const token = await getAuthToken();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${baseUrl}${endpoint}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options?.headers,
      },
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status}: ${errText || res.statusText || 'Request failed'}`);
    }

    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return await res.json();
    }
    return (await res.text()) as unknown as T;
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error(`Request timeout (${timeoutMs}ms) connecting to ${endpoint}`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}


export const desktopApi = {
  getProjects: async (): Promise<ProjectItem[]> => {
    return await safeFetch('/projects');
  },

  getModelScores: async (): Promise<ModelUtilityScore[]> => {
    return await safeFetch('/models');
  },

  listTriage: async (status?: string): Promise<TaskSummary[]> => {
    return await safeFetch(status ? `/triage?status=${status}` : '/triage');
  },

  getTaskDetail: async (taskId: string): Promise<TaskDetail> => {
    return await safeFetch(`/tasks/${taskId}`);
  },

  reviewTask: async (taskId: string, action: 'approve' | 'reject', notes: string) => {
    return await safeFetch(`/triage/${taskId}/review`, {
      method: 'POST',
      body: JSON.stringify({ action, founder_notes: notes }),
    });
  },

  getEmergencyStop: async (): Promise<EmergencyStopState> => {
    return await safeFetch('/emergency-stop');
  },

  toggleEmergencyStop: async (enable: boolean, reason: string): Promise<EmergencyStopState> => {
    return await safeFetch('/emergency-stop', {
      method: 'POST',
      body: JSON.stringify({ enable_stop: enable, reason }),
    });
  },

  getEvaMeetingToken: async (
    room: string,
    identity = 'Ajay (Founder)',
    token?: string
  ): Promise<{ token: string; room_name?: string }> => {
    const rootBase = getApiBaseUrl().replace('/api/v1/mobile', '');
    const authToken = token || (await getAuthToken());
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
      // Local dev fallback
    }
    return { token: 'simulated_webrtc_token', room_name: room };
  },

  createMeetingInvite: async (
    room: string,
    identity = 'Client',
    token?: string
  ): Promise<{ invite_token: string; invite_url: string }> => {
    const rootBase = getApiBaseUrl().replace('/api/v1/mobile', '');
    const authToken = token || (await getAuthToken());
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
      // Local dev fallback
    }
    return {
      invite_token: 'client_invite_token',
      invite_url: `/meet#invite=${encodeURIComponent(room)}`,
    };
  },

  getCommandNode: async (): Promise<CommandNodeScreenData> => {
    return await safeFetch('/command-node');
  },

  getSecurityEnclave: async (): Promise<SecurityEnclaveScreenData> => {
    return await safeFetch('/security-enclave');
  },

  getMeetingSetup: async (room = 'alphabrain-executive-briefing'): Promise<MeetingSetupScreenData> => {
    return await safeFetch(`/meet/setup?room=${encodeURIComponent(room)}`);
  }
};

