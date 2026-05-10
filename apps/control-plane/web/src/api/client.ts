const BASE = (import.meta.env.VITE_CONTROL_PLANE_BASE as string) || '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  const token = localStorage.getItem('yunmon.accessToken');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail: string;
    try {
      const payload = await response.json();
      detail = payload.detail || payload.error || JSON.stringify(payload);
    } catch {
      detail = await response.text();
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Record<string, unknown>>('/healthz'),
  getConfig: () => request<{ ok: boolean; config: Record<string, any> }>('/api/v1/config'),
  putConfig: (config: Record<string, any>) =>
    request<Record<string, unknown>>('/api/v1/config', {
      method: 'PUT',
      body: JSON.stringify({ config }),
    }),
  applyConfig: (config?: Record<string, any>) =>
    request<Record<string, unknown>>('/api/v1/config/apply', {
      method: 'POST',
      body: JSON.stringify({ config: config ?? null }),
    }),
  listServices: () => request<Record<string, unknown>>('/api/v1/system/services'),
  runtime: () => request<Record<string, unknown>>('/api/v1/system/runtime'),
  reloadPrometheus: () =>
    request<Record<string, unknown>>('/api/v1/system/prometheus/reload', { method: 'POST' }),
  restart: (payload: { build: boolean; includeControlPlane: boolean }) =>
    request<{ ok: boolean; jobId: string }>('/api/v1/system/restart', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  applications: () => request<Record<string, unknown>>('/api/v1/applications/discovery'),
  metricCatalog: () => request<Record<string, unknown>>('/api/v1/metrics/catalog'),
  syncMetricCatalog: () =>
    request<Record<string, unknown>>('/api/v1/metrics/catalog/sync', { method: 'POST' }),
  listSnapshots: () =>
    request<{ ok: boolean; snapshots: Array<Record<string, unknown>> }>(
      '/api/v1/audit/snapshots',
    ),
  getSnapshot: (id: string) =>
    request<{ ok: boolean; snapshot: Record<string, unknown> }>(`/api/v1/audit/snapshots/${id}`),
  rollback: (id: string) =>
    request<Record<string, unknown>>(`/api/v1/audit/snapshots/${id}/rollback`, {
      method: 'POST',
    }),
  listJobs: () => request<{ ok: boolean; jobs: Array<Record<string, unknown>> }>('/api/v1/jobs'),
  getJob: (id: string) =>
    request<{ ok: boolean; job: Record<string, unknown> }>(`/api/v1/jobs/${id}`),
  login: (username: string, password: string) =>
    request<{ ok: boolean; accessToken: string; refreshToken: string; expiresIn: number }>(
      '/api/v1/auth/login',
      { method: 'POST', body: JSON.stringify({ username, password }) },
    ),
};

export type Api = typeof api;
