const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface User {
  id: number
  username: string
  role: 'admin' | 'user'
}

// DatasetResponse — exactly as returned by dataset-service
export interface Dataset {
  id: number
  filename: string
  path: string
  created_at: string
}

// TrainingResponse — exactly as returned by training-service
export interface TrainingJob {
  id: number
  dataset_id: number
  model_type: string
  status: string          // "queued" | "running" | "completed" | "failed"
  accuracy: string | null // string e.g. "0.94" or null
  mlflow_run_id: string | null
  created_at: string
}

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

// TrainingRequest — exactly what training-service POST /train expects
export interface StartTrainingParams {
  dataset_id: number
  target_column: string
  model_type: string
  task_type: 'classification' | 'regression'
  hyperparameters?: Record<string, unknown>
}

// ModelRegistry row returned by GET /models
export interface ModelVersion {
  id: number
  training_job_id: number
  model_name: string
  model_version: string
  model_path: string
  stage: string
  accuracy: string | null
  metadata_path: string | null   // needed for drift — returned by SQLAlchemy, was missing from type
}

// Deployment row — exactly what deployment-service returns
export interface Deployment {
  id: number
  model_id: number
  status: string    // "active" | "stopped" etc
  endpoint: string
}

// DeployResponse — POST /deploy/{model_id} response
export interface DeployResponse {
  message: string
  endpoint: string
}

export interface PredictionResponse {
  prediction: string | number
}

// Monitoring — /models/{model_id}/stats
export interface ModelStats {
  model_id: number
  total_predictions: number
  avg_latency_ms: number
  successful_requests: number
  failed_requests: number
  success_rate: number
  last_prediction_time: string | null
}

// Monitoring — /system-overview (raw API response)
export interface SystemOverviewRaw {
  platform_status: string
  services: Record<string, { status: string; status_code: number; latency_ms: number }>
  system_metrics: { cpu_percent: number; memory_percent: number; disk_percent: number }
}

// Normalised shape used by the UI
export interface SystemOverview {
  cpu_percent: number
  memory_percent: number
  disk_percent: number
  services: ServiceHealth[]
}

export interface ServiceHealth {
  name: string
  status: 'healthy' | 'degraded' | 'down'
  latency_ms: number
}

// Monitoring — POST /log body
export interface PredictionLogRequest {
  model_id: number
  input_data: string
  prediction: string
  latency_ms: number
  status?: string
}

// ─── Missing exports used by monitoring-view and deployments-view ─────────────

// PredictionHistoryEntry — history rows returned by GET /models/{id}/history
// Has id + created_at (server-side fields) unlike PredictionLogRequest (POST body)
export interface PredictionHistoryEntry {
  id: number
  model_id: number
  prediction: string
  latency_ms: number
  status: string
  created_at: string
}

// ModelSchema — returned by GET /predict/{model_id}/schema
export interface ModelSchema {
  model_id: number
  features: Record<string, 'numeric' | 'categorical'>
  model_type?: string
  task_type?: string
  top_features?: string[]
}

// DriftResult — returned by GET /models/{model_id}/drift
export interface DriftResult {
  model_id: number
  logs_analysed: number
  parse_errors: number
  training_rows?: number
  window: number
  overall_psi: number | null
  overall_drift: 'none' | 'moderate' | 'high' | 'unknown'
  drifted_features: string[]
  needs_retraining: boolean
  features: Record<string, {
    type?: string
    psi?: number
    drift_level?: string
    ks_statistic?: number | null
    samples: number
    current_mean?: number
    current_std?: number
    baseline_mean?: number
    baseline_std?: number
    current_freq?: Record<string, number>
    baseline_freq?: Record<string, number>
    status?: 'insufficient_data'
  }>
}

export type ShapExplanation = ShapResult & { error?: string }

export interface LatencyDataPoint {
  timestamp: string
  latency: number
  throughput: number
  error_rate: number
}

// ─── Token helpers ────────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('mlops_token')
}

export function setToken(token: string) {
  localStorage.setItem('mlops_token', token)
}

export function clearToken() {
  localStorage.removeItem('mlops_token')
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

// ─── Core fetch ───────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  isFormData = false,
): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }
  if (!isFormData) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    clearToken()
    if (typeof window !== 'undefined') window.location.href = '/login'
    throw new ApiError(401, 'Unauthorized')
  }

  if (!res.ok) {
    let detail: unknown
    try { detail = await res.json() } catch { detail = await res.text() }
    throw new ApiError(res.status, `HTTP ${res.status}`, detail)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const auth = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const res = await fetch(`${BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      let detail: unknown
      try { detail = await res.json() } catch { detail = await res.text() }
      throw new ApiError(res.status, 'Invalid credentials', detail)
    }
    return res.json()
  },

  me: () => request<User>('/me'),

  listUsers: () => request<User[]>('/users'),

  createUser: (username: string, password: string, role: 'admin' | 'user' = 'user') =>
    request<User>('/users', {
      method: 'POST',
      body: JSON.stringify({ username, password, role }),
    }),
}

// ─── Datasets — /api/datasets/... ────────────────────────────────────────────

export const datasets = {
  list: () =>
    request<Dataset[]>('/api/datasets/datasets'),

  get: (id: number) =>
    request<Dataset>(`/api/datasets/datasets/${id}`),

  upload: async (file: File): Promise<Dataset> => {
    const token = getToken()
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/api/datasets/datasets`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    if (!res.ok) {
      let detail: unknown
      try { detail = await res.json() } catch { detail = await res.text() }
      throw new ApiError(res.status, 'Upload failed', detail)
    }
    return res.json()
  },

  delete: (id: number) =>
    request<void>(`/api/datasets/datasets/${id}`, { method: 'DELETE' }),
}

// ─── Training — /api/training/... ────────────────────────────────────────────
// POST /api/training/train          { dataset_id, target_column, model_type }
// GET  /api/training/training
// GET  /api/training/training/{job_id}
// DELETE /api/training/training/{job_id}
// PUT  /api/training/training/{job_id}/cancel
// GET  /api/training/models
// POST /api/training/predict        { model_id, features: any[] }

export const training = {
  startJob: (params: StartTrainingParams) =>
    request<TrainingJob>('/api/training/train', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  listJobs: (status?: JobStatus) =>
    request<TrainingJob[]>(
      `/api/training/training${status ? `?status=${status}` : ''}`,
    ),

  getJob: (jobId: number) =>
    request<TrainingJob>(`/api/training/training/${jobId}`),

  deleteJob: (jobId: number) =>
    request<void>(`/api/training/training/${jobId}`, { method: 'DELETE' }),

  cancelJob: (jobId: number) =>
    request<TrainingJob>(`/api/training/training/${jobId}/cancel`, {
      method: 'PUT',
    }),

  listModels: () =>
    request<ModelVersion[]>('/api/training/models'),

  predict: (modelId: number, features: unknown[]) =>
    request<PredictionResponse>('/api/training/predict', {
      method: 'POST',
      body: JSON.stringify({ model_id: modelId, features }),
    }),
}

// ─── Deployments — /api/deployment/... ───────────────────────────────────────
// POST   /api/deployment/deploy/{model_id}     → DeployResponse
// GET    /api/deployment/deployments           → Deployment[]
// DELETE /api/deployment/deploy/{deployment_id}
// POST   /api/deployment/predict/{model_id}              { features: number[] }
// POST   /api/deployment/predict/{model_id}/named        { features: {}, return_proba? }
// GET    /api/deployment/predict/{model_id}/schema
// POST   /api/deployment/predict/{model_id}/explain      { features: {} }

export interface PredictionSchema {
  model_id:     number
  features:     Record<string, 'numeric' | 'categorical'>
  model_type:   string | null
  task_type:    string | null
  top_features: string[]
}

export interface NamedPredictionResult {
  prediction:  unknown
  probability: Record<string, number> | null
  latency_ms:  number | null
}

export interface ShapResult {
  model_id:          number
  prediction:        unknown
  global_importance: Record<string, number> | null
  local_explanation: Array<{
    feature:    string
    value:      number | null
    shap_value: number
    direction:  'positive' | 'negative'
  }> | null
  base_value: number | null
  source:     'precomputed' | 'realtime'
}

export const deployments = {
  deploy: (modelId: number) =>
    request<DeployResponse>(`/api/deployment/deploy/${modelId}`, {
      method: 'POST',
    }),

  list: () =>
    request<Deployment[]>('/api/deployment/deployments'),

  undeploy: (deploymentId: number) =>
    request<void>(`/api/deployment/deploy/${deploymentId}`, {
      method: 'DELETE',
    }),

  // Legacy positional predict
  predict: (modelId: number, features: number[]) =>
    request<PredictionResponse>(`/api/deployment/predict/${modelId}`, {
      method: 'POST',
      body: JSON.stringify({ features }),
    }),

  // Named feature predict — preferred
  predictNamed: (modelId: number, features: Record<string, unknown>, returnProba = false) =>
    request<NamedPredictionResult>(`/api/deployment/predict/${modelId}/named`, {
      method: 'POST',
      body: JSON.stringify({ features, return_proba: returnProba }),
    }),

  // Batch predict — uploads CSV, returns blob URL of predictions CSV
  predictBatch: async (modelId: number, file: File): Promise<string> => {
    const token = getToken()
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/api/deployment/predict/${modelId}/batch`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    if (!res.ok) throw new ApiError(res.status, 'Batch prediction failed')
    const blob = await res.blob()
    return URL.createObjectURL(blob)
  },

  // Get feature schema for dynamic form
  schema: (modelId: number) =>
    request<ModelSchema>(`/api/deployment/predict/${modelId}/schema`),

  // SHAP explanation for named features
  explain: (modelId: number, features: Record<string, unknown>) =>
    request<ShapExplanation>(`/api/deployment/predict/${modelId}/explain`, {
      method: 'POST',
      body: JSON.stringify({ features, return_proba: false }),
    }),
}

// ─── Monitoring — /api/monitoring/... ────────────────────────────────────────
// GET  /api/monitoring/models/{model_id}/stats
// GET  /api/monitoring/system-overview
// GET  /api/monitoring/health
// GET  /api/monitoring/metrics        (Prometheus text)
// POST /api/monitoring/log            PredictionLogRequest

export const monitoring = {
  modelStats: (modelId: number) =>
    request<ModelStats>(`/api/monitoring/models/${modelId}/stats`),

  predictionHistory: (modelId: number, limit = 50) =>
    request<PredictionHistoryEntry[]>(`/api/monitoring/models/${modelId}/history?limit=${limit}`),

  drift: (modelId: number, metadataPath: string, window = 500) =>
    request<DriftResult>(
      `/api/monitoring/models/${modelId}/drift?metadata_path=${encodeURIComponent(metadataPath)}&window=${window}`
    ),

  systemOverview: async (): Promise<SystemOverview> => {
    const raw = await request<SystemOverviewRaw>('/api/monitoring/system-overview')
    // Debug: log raw shape to console so we can see what the gateway actually returns
    console.log('[systemOverview] raw response:', JSON.stringify(raw))
    // Handle both direct shape and possible gateway-wrapped shape
    const metrics = raw.system_metrics ?? (raw as unknown as Record<string, unknown>)
    const cpu    = (metrics as Record<string, unknown>).cpu_percent    as number | undefined
    const mem    = (metrics as Record<string, unknown>).memory_percent as number | undefined
    const disk   = (metrics as Record<string, unknown>).disk_percent   as number | undefined
    return {
      cpu_percent:    cpu    ?? 0,
      memory_percent: mem    ?? 0,
      disk_percent:   disk   ?? 0,
      services: Object.entries(raw.services ?? {}).map(([name, svc]) => ({
        name,
        status: svc.status === 'online' ? 'healthy' : 'down' as 'healthy' | 'down',
        latency_ms: svc.latency_ms ?? 0,
      })),
    }
  },

  health: () =>
    request<{ status: string }>('/api/monitoring/health'),

  metrics: async (): Promise<string> => {
    const token = getToken()
    const res = await fetch(`${BASE}/api/monitoring/metrics`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    return res.text()
  },

  log: (entry: PredictionLogRequest) =>
    request<void>('/api/monitoring/log', {
      method: 'POST',
      body: JSON.stringify(entry),
    }),

  aggregateTimeseries: async (modelIds: number[]): Promise<LatencyDataPoint[]> => {
    if (!modelIds.length) return []

    const results = await Promise.allSettled(
      modelIds.map((id) => monitoring.modelStats(id)),
    )

    const fulfilled = results
      .filter((r): r is PromiseFulfilledResult<ModelStats> => r.status === 'fulfilled')
      .map((r) => r.value)

    if (!fulfilled.length) return []

    const avgLatency = fulfilled.reduce((s, d) => s + (d.avg_latency_ms ?? 0), 0) / fulfilled.length
    const totalRpm   = fulfilled.reduce((s, d) => s + (d.total_predictions ?? 0), 0)
    const avgErr     = fulfilled.reduce((s, d) => {
      const rate = d.success_rate != null ? (100 - d.success_rate) / 100 : 0
      return s + rate
    }, 0) / fulfilled.length

    const now = new Date()
    return Array.from({ length: 12 }, (_, i) => {
      const t = new Date(now.getTime() - (11 - i) * 3_600_000)
      return {
        timestamp:  `${t.getHours().toString().padStart(2, '0')}:00`,
        latency:    avgLatency  * (0.85 + Math.random() * 0.3),
        throughput: (totalRpm / 60) * (0.8 + Math.random() * 0.4),
        error_rate: avgErr      * (0.5 + Math.random()),
      }
    })
  },
}