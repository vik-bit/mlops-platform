import { useState, useEffect, useCallback, useRef } from 'react'
import {
  training, deployments, monitoring, datasets, auth,
  TrainingJob, Deployment, ModelStats, SystemOverview,
  Dataset, LatencyDataPoint, JobStatus, ModelVersion, User,
} from './api'

// ─── Generic polling hook ─────────────────────────────────────────────────────

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled = true,
) {
  const [data, setData]       = useState<T | null>(null)
  const [error, setError]     = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)
  const timerRef              = useRef<ReturnType<typeof setInterval> | null>(null)
  const fetcherRef            = useRef(fetcher)
  fetcherRef.current          = fetcher

  const run = useCallback(async () => {
    try {
      const result = await fetcherRef.current()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e as Error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!enabled) { setLoading(false); return }
    run()
    timerRef.current = setInterval(run, intervalMs)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [run, intervalMs, enabled])

  return { data, error, loading, refresh: run }
}

// ─── Current user ─────────────────────────────────────────────────────────────

export function useCurrentUser() {
  const fetcher = useCallback(() => auth.me(), [])
  return usePolling<User>(fetcher, 300_000)
}

// ─── Training jobs ────────────────────────────────────────────────────────────

export function useTrainingJobs(statusFilter?: JobStatus) {
  const [jobs, setJobs]       = useState<TrainingJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<Error | null>(null)

  const hasActive    = jobs.some(j => j.status === 'running' || j.status === 'queued')
  const pollInterval = hasActive ? 4_000 : 30_000

  const fetcher = useCallback(() => training.listJobs(statusFilter), [statusFilter])
  const { data, error: pollError, loading: pollLoading, refresh } = usePolling(fetcher, pollInterval)

  useEffect(() => {
    if (data)      setJobs(data)
    if (pollError) setError(pollError)
    setLoading(pollLoading)
  }, [data, pollError, pollLoading])

  return { jobs, loading, error, refresh }
}

// ─── Single job ───────────────────────────────────────────────────────────────

export function useTrainingJob(jobId: number | null) {
  const fetcher = useCallback(() => training.getJob(jobId!), [jobId])
  return usePolling<TrainingJob>(fetcher, 3_000, jobId !== null)
}

// ─── Model registry ───────────────────────────────────────────────────────────

export function useModels() {
  const fetcher = useCallback(() => training.listModels(), [])
  return usePolling<ModelVersion[]>(fetcher, 30_000)
}

// ─── Deployments ──────────────────────────────────────────────────────────────

export function useDeployments() {
  const fetcher = useCallback(() => deployments.list(), [])
  return usePolling<Deployment[]>(fetcher, 10_000)
}

// ─── System health ────────────────────────────────────────────────────────────
// monitoring.systemOverview() now returns a normalised SystemOverview directly

export function useSystemHealth() {
  const fetcher = useCallback(() => monitoring.systemOverview(), [])
  return usePolling<SystemOverview>(fetcher, 15_000)
}

// ─── Datasets ─────────────────────────────────────────────────────────────────

export function useDatasets() {
  const fetcher = useCallback(() => datasets.list(), [])
  return usePolling<Dataset[]>(fetcher, 60_000)
}

// ─── Per-model stats ──────────────────────────────────────────────────────────

export function useModelStats(modelId: number | null) {
  const fetcher = useCallback(() => monitoring.modelStats(modelId!), [modelId])
  return usePolling<ModelStats>(fetcher, 30_000, modelId !== null)
}

// ─── Latency timeseries ───────────────────────────────────────────────────────

export function useLatencyTimeseries(modelIds: number[]) {
  const [series, setSeries]   = useState<LatencyDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const key = modelIds.join(',')

  useEffect(() => {
    if (!modelIds.length) { setLoading(false); return }
    setLoading(true)
    monitoring.aggregateTimeseries(modelIds)
      .then(setSeries)
      .catch(console.error)
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return { series, loading }
}

// ─── Dashboard aggregate ──────────────────────────────────────────────────────

export function useDashboard() {
  const { jobs,           loading: jobsLoading,        error: jobsError, refresh: refreshJobs }  = useTrainingJobs()
  const { data: depList,  loading: deploymentsLoading, refresh: refreshDeployments }             = useDeployments()
  const { data: modelList,loading: modelsLoading }                                               = useModels()
  const { data: system,   loading: systemLoading }                                               = useSystemHealth()
  const { data: dsList,   loading: datasetsLoading }                                             = useDatasets()

  const modelIds = (modelList ?? []).map(m => m.id)
  const { series: latencySeries, loading: seriesLoading } = useLatencyTimeseries(modelIds)

  const refresh = useCallback(() => { refreshJobs(); refreshDeployments() }, [refreshJobs, refreshDeployments])

  const loading = jobsLoading || deploymentsLoading || modelsLoading || systemLoading || datasetsLoading

  const runningJobs   = jobs.filter(j => j.status === 'running').length
  const completedJobs = jobs.filter(j => j.status === 'completed').length
  const failedJobs    = jobs.filter(j => j.status === 'failed').length

  // accuracy is a string | null  — parse safely
  const accurateJobs = jobs.filter(j => j.accuracy != null && !isNaN(parseFloat(j.accuracy!)))
  const avgAccuracy  = accurateJobs.length
    ? accurateJobs.reduce((s, j) => s + parseFloat(j.accuracy!), 0) / accurateJobs.length
    : null

  const activeDeployments = (depList ?? []).filter(d => d.status === 'active')

  return {
    jobs,
    deployments:   depList    ?? [],
    models:        modelList  ?? [],
    system,
    datasets:      dsList     ?? [],
    latencySeries,
    loading,
    seriesLoading,
    error:         jobsError,
    refresh,
    stats: {
      totalJobs:         jobs.length,
      runningJobs,
      completedJobs,
      failedJobs,
      avgAccuracy,
      activeDeployments: activeDeployments.length,
      totalDeployments:  (depList  ?? []).length,
      totalDatasets:     (dsList   ?? []).length,
      totalModels:       (modelList ?? []).length,
    },
  }
}