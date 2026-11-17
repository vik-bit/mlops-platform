'use client'

import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { GitBranch, RotateCcw, ArrowUpCircle, XCircle, RefreshCw } from 'lucide-react'
import {
  lifecycle,
  LifecycleEvent,
  ModelVersion,
  Rollout,
  RolloutMode,
} from '@/lib/api'

// Shadow/canary rollouts for one deployment, and its lifecycle events (promotions, rollbacks,
// drift, retrains, gate results). Data comes from deployment-service app/routes/lifecycle.py.

const EVENT_STYLE: Record<string, string> = {
  promoted: 'text-green-700 bg-green-100',
  rolled_back: 'text-red-700 bg-red-100',
  gate_failed: 'text-red-700 bg-red-100',
  retrain_failed: 'text-red-700 bg-red-100',
  promotion_failed: 'text-red-700 bg-red-100',
  gate_passed: 'text-green-700 bg-green-100',
  drift_detected: 'text-amber-700 bg-amber-100',
  retrain_queued: 'text-amber-700 bg-amber-100',
  canary_started: 'text-blue-700 bg-blue-100',
  shadow_started: 'text-blue-700 bg-blue-100',
  shadow_passed: 'text-blue-700 bg-blue-100',
}

function fmtTime(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

function pct(v: number | null | undefined) {
  return v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`
}

function num(v: number | null | undefined, digits = 1) {
  return v === null || v === undefined ? '—' : v.toFixed(digits)
}

export default function RolloutPanel({
  deploymentId,
  stableModelId,
  models,
  onChanged,
}: {
  deploymentId: number
  stableModelId: number
  models: ModelVersion[]
  onChanged?: () => void
}) {
  const [rollouts, setRollouts] = useState<Rollout[]>([])
  const [events, setEvents] = useState<LifecycleEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [candidate, setCandidate] = useState('')
  const [mode, setMode] = useState<RolloutMode>('canary')
  const [traffic, setTraffic] = useState(10)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [r, e] = await Promise.all([lifecycle.rollouts(deploymentId), lifecycle.events(deploymentId, 30)])
      setRollouts(r)
      setEvents(e)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load rollouts')
    } finally {
      setLoading(false)
    }
  }, [deploymentId])

  useEffect(() => {
    load()
    const t = setInterval(load, 5000) // the controller acts every few seconds
    return () => clearInterval(t)
  }, [load])

  const active = rollouts.find(r => r.status === 'active')

  async function start() {
    if (!candidate) return
    setBusy(true)
    try {
      await lifecycle.startRollout(deploymentId, {
        candidate_model_id: parseInt(candidate),
        mode,
        traffic_percent: mode === 'canary' ? traffic : 0,
      })
      setCandidate('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start rollout')
    } finally {
      setBusy(false)
    }
  }

  async function finish(action: 'promote' | 'rollback' | 'cancel') {
    if (!active) return
    setBusy(true)
    try {
      await lifecycle.finishRollout(active.id, action)
      await load()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not ${action}`)
    } finally {
      setBusy(false)
    }
  }

  const m = active?.last_metrics

  return (
    <div className="p-6 space-y-6" style={{ borderTop: '1px solid #ebebea' }}>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <GitBranch className="w-4 h-4" /> Rollouts
        </h4>
        <button onClick={load} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : active ? (
        <div className="rounded-lg border border-border p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold text-blue-700 bg-blue-100">
              {active.mode === 'canary' ? `canary ${active.traffic_percent}%` : 'shadow'}
            </span>
            <span className="text-foreground">
              Model #{active.stable_model_id} (stable) → #{active.candidate_model_id} (candidate)
            </span>
            <span className="text-muted-foreground text-xs">since {fmtTime(active.started_at)}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <Stat label="Candidate requests" value={m ? String(m.candidate_requests) : '—'} />
            <Stat label="Error rate (cand / stable)" value={m ? `${pct(m.candidate_error_rate)} / ${pct(m.stable_error_rate)}` : '—'} />
            <Stat label="p95 ms (cand / stable)" value={m ? `${num(m.candidate_p95_ms)} / ${num(m.stable_p95_ms)}` : '—'} />
            <Stat label="Prediction PSI" value={m ? num(m.prediction_psi, 3) : '—'} />
          </div>
          <div className="flex gap-2">
            <ActionButton onClick={() => finish('promote')} disabled={busy} icon={<ArrowUpCircle className="w-3.5 h-3.5" />} label="Promote" />
            <ActionButton onClick={() => finish('rollback')} disabled={busy} icon={<RotateCcw className="w-3.5 h-3.5" />} label="Roll back" danger />
            <ActionButton onClick={() => finish('cancel')} disabled={busy} icon={<XCircle className="w-3.5 h-3.5" />} label="Cancel" />
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Candidate model</label>
            <select value={candidate} onChange={e => setCandidate(e.target.value)}
              className="h-8 px-2 bg-secondary border border-border rounded-lg text-xs text-foreground">
              <option value="">Select…</option>
              {models.filter(x => x.id !== stableModelId).map(x => (
                <option key={x.id} value={x.id}>#{x.id} {x.model_name} {x.model_version} · {x.stage}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Mode</label>
            <select value={mode} onChange={e => setMode(e.target.value as RolloutMode)}
              className="h-8 px-2 bg-secondary border border-border rounded-lg text-xs text-foreground">
              <option value="canary">Canary</option>
              <option value="shadow">Shadow</option>
            </select>
          </div>
          {mode === 'canary' && (
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Traffic %</label>
              <input type="number" min={1} max={100} value={traffic}
                onChange={e => setTraffic(Number(e.target.value))}
                className="h-8 w-20 px-2 bg-secondary border border-border rounded-lg text-xs text-foreground" />
            </div>
          )}
          <button onClick={start} disabled={busy || !candidate}
            className="h-8 px-3 rounded-lg bg-primary text-primary-foreground text-xs font-medium disabled:opacity-60">
            Start rollout
          </button>
        </div>
      )}

      <div>
        <h4 className="text-sm font-semibold text-foreground mb-2">Lifecycle events</h4>
        {events.length === 0 ? (
          <p className="text-xs text-muted-foreground">No events yet.</p>
        ) : (
          <ul className="space-y-1.5 max-h-72 overflow-auto">
            {events.map(ev => (
              <li key={ev.id} className="text-xs flex flex-wrap items-baseline gap-2">
                <span className="text-muted-foreground w-36 shrink-0">{fmtTime(ev.created_at)}</span>
                <span className={`px-2 py-0.5 rounded-full font-semibold ${EVENT_STYLE[ev.event_type] ?? 'text-gray-600 bg-gray-100'}`}>
                  {ev.event_type.replace(/_/g, ' ')}
                </span>
                {(ev.from_model_id || ev.to_model_id) && (
                  <span className="text-foreground">
                    {ev.from_model_id ? `#${ev.from_model_id}` : ''}{ev.from_model_id && ev.to_model_id ? ' → ' : ''}{ev.to_model_id ? `#${ev.to_model_id}` : ''}
                  </span>
                )}
                {ev.reason && <span className="text-muted-foreground break-all">{ev.reason}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-secondary/40 rounded-lg p-2">
      <p className="text-muted-foreground">{label}</p>
      <p className="text-foreground font-semibold mt-0.5">{value}</p>
    </div>
  )
}

function ActionButton({ onClick, disabled, icon, label, danger }: {
  onClick: () => void; disabled: boolean; icon: ReactNode; label: string; danger?: boolean
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-border transition disabled:opacity-60 ${danger ? 'hover:bg-red-50 hover:text-red-500' : 'hover:bg-secondary'} text-foreground`}>
      {icon}{label}
    </button>
  )
}
