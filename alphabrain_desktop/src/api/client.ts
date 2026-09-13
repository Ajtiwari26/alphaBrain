import {
  EmergencyStopState,
  ModelUtilityScore,
  ProjectItem,
  TaskDetail,
  TaskSummary,
} from '../types';

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const custom = localStorage.getItem('alpha_api_base');
    if (custom) return custom;
    if (window.location.port === '5173') {
      return '/api/v1/mobile';
    }
  }
  return 'http://localhost:8000/api/v1/mobile';
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
    return sessionStorage.getItem('alpha_api_token') || localStorage.getItem('alpha_api_token') || '';
  }
  return '';
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

  getEvaMeetingToken: async (room: string): Promise<{ token: string; room_name?: string }> => {
    return await safeFetch(`/meet/token?room=${encodeURIComponent(room)}`);
  },
};

