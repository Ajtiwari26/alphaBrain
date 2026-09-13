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

export function getAuthToken(): string {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('alpha_api_token') || (import.meta.env?.VITE_DEFAULT_AUTH_TOKEN ?? '');
  }
  return '';
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
    const errText = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${errText || res.statusText || 'Request failed'}`);
  }
  return await res.json();
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
};

