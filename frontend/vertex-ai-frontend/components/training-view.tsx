'use client'

import { useState } from 'react'
import { Plus, Trash2, AlertCircle, ChevronDown, ChevronUp, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTrainingJobs, useDatasets } from '@/lib/hooks'
import { training, TrainingJob, StartTrainingParams } from '@/lib/api'

// ─── Model catalogue ──────────────────────────────────────────────────────────

type ParamDef = {
  key: string; label: string; type: 'number' | 'select'
  default: number | string; options?: string[]
  min?: number; max?: number; step?: number; description: string
}

const MODEL_PARAMS: Record<string, { label: string; description: string; params: ParamDef[] }> = {
  random_forest: {
    label: 'Random Forest',
    description: 'Ensemble of decision trees — robust, handles missing data well.',
    params: [
      { key: 'n_estimators',      label: 'Trees',       type: 'number', default: 100, min: 10,    max: 1000, step: 10,   description: 'More trees = better accuracy, slower training' },
      { key: 'max_depth',         label: 'Max Depth',   type: 'number', default: 10,  min: 1,     max: 50,   step: 1,    description: 'Limit depth to prevent overfitting' },
      { key: 'min_samples_split', label: 'Min Split',   type: 'number', default: 2,   min: 2,     max: 20,   step: 1,    description: 'Min samples required to split a node' },
      { key: 'min_samples_leaf',  label: 'Min Leaf',    type: 'number', default: 1,   min: 1,     max: 20,   step: 1,    description: 'Min samples at each leaf node' },
    ],
  },
  gradient_boosting: {
    label: 'Gradient Boosting',
    description: 'Sequentially builds trees correcting prior errors.',
    params: [
      { key: 'n_estimators',  label: 'Trees',         type: 'number', default: 100,  min: 10,    max: 500,  step: 10,   description: 'Number of boosting stages' },
      { key: 'learning_rate', label: 'Learning Rate', type: 'number', default: 0.1,  min: 0.001, max: 1.0,  step: 0.01, description: 'Shrinks each tree contribution' },
      { key: 'max_depth',     label: 'Max Depth',     type: 'number', default: 3,    min: 1,     max: 10,   step: 1,    description: 'Keep 3–5 for boosting' },
    ],
  },
  logistic_regression: {
    label: 'Logistic Regression',
    description: 'Fast linear model — great baseline. Maps to Ridge for regression.',
    params: [
      { key: 'C',        label: 'Regularisation (C)', type: 'number', default: 1.0,  min: 0.001, max: 100,  step: 0.1,  description: 'Smaller = more regularised' },
      { key: 'max_iter', label: 'Max Iterations',     type: 'number', default: 1000, min: 100,   max: 5000, step: 100,  description: 'Iterations for solver convergence' },
    ],
  },
  svm: {
    label: 'SVM',
    description: 'Effective in high-dimensional spaces. Can be slow on large datasets.',
    params: [
      { key: 'C',      label: 'C',      type: 'number', default: 1.0, min: 0.001, max: 100, step: 0.1, description: 'Higher = less margin' },
      { key: 'kernel', label: 'Kernel', type: 'select', default: 'rbf', options: ['rbf', 'linear', 'poly', 'sigmoid'], description: 'rbf works best for most problems' },
    ],
  },
  knn: {
    label: 'KNN',
    description: 'Simple instance-based learner — intuitive but scale-sensitive.',
    params: [
      { key: 'n_neighbors', label: 'K',       type: 'number', default: 5,         min: 1, max: 50, step: 1, description: 'Odd numbers avoid ties' },
      { key: 'weights',     label: 'Weights', type: 'select', default: 'uniform', options: ['uniform', 'distance'], description: '"distance" gives closer neighbours more weight' },
    ],
  },
  decision_tree: {
    label: 'Decision Tree',
    description: 'Highly interpretable — see exactly why each prediction was made.',
    params: [
      { key: 'max_depth',         label: 'Max Depth', type: 'number', default: 5, min: 1, max: 50, step: 1, description: 'Shallow = interpretable, deep = may overfit' },
      { key: 'min_samples_split', label: 'Min Split', type: 'number', default: 2, min: 2, max: 20, step: 1, description: 'Min samples to split a node' },
    ],
  },
  xgboost: {
    label: 'XGBoost',
    description: 'State-of-the-art gradient boosting — wins most tabular competitions.',
    params: [
      { key: 'n_estimators',  label: 'Estimators',    type: 'number', default: 100, min: 10,    max: 1000, step: 10,   description: 'Boosting rounds' },
      { key: 'learning_rate', label: 'Learning Rate', type: 'number', default: 0.1, min: 0.001, max: 1.0,  step: 0.01, description: 'Lower rate + more trees = better generalisation' },
      { key: 'max_depth',     label: 'Max Depth',     type: 'number', default: 6,   min: 1,     max: 15,   step: 1,    description: 'Max depth per tree' },
    ],
  },
  lightgbm: {
    label: 'LightGBM',
    description: 'Faster than XGBoost on large datasets — leaf-wise tree growth.',
    params: [
      { key: 'n_estimators',  label: 'Estimators',    type: 'number', default: 100, min: 10,    max: 1000, step: 10,   description: 'Boosting iterations' },
      { key: 'learning_rate', label: 'Learning Rate', type: 'number', default: 0.1, min: 0.001, max: 1.0,  step: 0.01, description: 'Lower = more iterations needed' },
      { key: 'max_depth',     label: 'Max Depth',     type: 'number', default: -1,  min: -1,    max: 20,   step: 1,    description: '-1 = unlimited' },
    ],
  },
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusPill(status: string) {
  const map: Record<string, string> = {
    running:   'text-blue-600 bg-blue-50 border border-blue-200',
    completed: 'text-green-700 bg-green-50 border border-green-200',
    failed:    'text-red-600 bg-red-50 border border-red-200',
    queued:    'text-amber-600 bg-amber-50 border border-amber-200',
    cancelled: 'text-gray-500 bg-gray-50 border border-gray-200',
  }
  return map[status] ?? map.queued
}

function fmtPct(v: string | number | null | undefined) {
  if (v == null) return null
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (isNaN(n)) return null
  // accuracy comes as a 0–1 decimal string from the backend
  return `${(n * 100).toFixed(1)}%`
}

function MetricBadge({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <div style={{ background: '#f8f8f6', border: '1px solid #ebebea', borderRadius: 8, padding: '8px 12px', minWidth: 80 }}>
      <div style={{ fontSize: 10, color: '#b8b8b4', textTransform: 'uppercase', letterSpacing: '.05em', fontWeight: 500, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: '#111' }}>{value}</div>
    </div>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function TrainingView() {
  const { jobs, loading, refresh } = useTrainingJobs()
  const { data: datasetList } = useDatasets()

  const [showModal, setShowModal]   = useState(false)
  const [showParams, setShowParams] = useState(true)
  const [form, setForm] = useState<{
    dataset_id: string; model_type: string; target_column: string
    task_type: 'classification' | 'regression'
  }>({ dataset_id: '', model_type: 'random_forest', target_column: '', task_type: 'classification' })
  const [hyperparams, setHyperparams] = useState<Record<string, string>>({})
  const [submitting, setSubmitting]   = useState(false)
  const [formError, setFormError]     = useState<string | null>(null)
  const [deleting, setDeleting]       = useState<number | null>(null)
  const [cancelling, setCancelling]   = useState<number | null>(null)

  const modelConfig = MODEL_PARAMS[form.model_type]

  const handleModelChange = (model_type: string) => {
    const defaults: Record<string, string> = {}
    MODEL_PARAMS[model_type]?.params.forEach(p => { defaults[p.key] = String(p.default) })
    setForm(f => ({ ...f, model_type }))
    setHyperparams(defaults)
  }

  const openModal = () => { handleModelChange(form.model_type); setShowModal(true) }

  const handleStart = async () => {
    if (!form.dataset_id)           { setFormError('Please select a dataset'); return }
    if (!form.target_column.trim()) { setFormError('Target column is required'); return }
    if (!form.model_type)           { setFormError('Please select a model'); return }

    setSubmitting(true); setFormError(null)

    const typedParams: Record<string, unknown> = {}
    modelConfig?.params.forEach(p => {
      const raw = hyperparams[p.key] ?? String(p.default)
      typedParams[p.key] = p.type === 'number' ? parseFloat(raw) : raw
    })

    try {
      await training.startJob({
        dataset_id:      parseInt(form.dataset_id),
        target_column:   form.target_column.trim(),
        model_type:      form.model_type,
        task_type:       form.task_type,
        hyperparameters: typedParams,
      } as StartTrainingParams)
      setShowModal(false)
      setForm({ dataset_id: '', model_type: 'random_forest', target_column: '', task_type: 'classification' })
      refresh()
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to start job')
    } finally { setSubmitting(false) }
  }

  return (
    <div className="flex-1 overflow-auto bg-white">
      {/* Header */}
      <div className="border-b border-border bg-white sticky top-0 z-10">
        <div className="px-8 py-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Training Jobs</h1>
            <p className="text-muted-foreground mt-1">Train models with custom algorithms and hyperparameters</p>
          </div>
          <Button onClick={openModal}><Plus className="w-4 h-4 mr-2" />New Training Job</Button>
        </div>
      </div>

      <div className="p-8">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: 'Total Jobs', value: jobs.length,                                          color: '#111' },
            { label: 'Running',    value: jobs.filter(j => j.status === 'running').length,   color: '#2563eb' },
            { label: 'Completed',  value: jobs.filter(j => j.status === 'completed').length, color: '#16a34a' },
          ].map(s => (
            <div key={s.label} className="bg-white border border-border rounded-xl p-5">
              <p className="text-muted-foreground text-sm mb-2">{s.label}</p>
              <p className="text-3xl font-bold" style={{ color: s.color }}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* Job list */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2].map(i => <div key={i} className="h-32 bg-secondary rounded-xl animate-pulse" />)}
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-border rounded-xl text-muted-foreground">
            <p className="font-medium mb-1">No training jobs yet</p>
            <p className="text-sm">Start your first job to see it here</p>
          </div>
        ) : (
          <div className="space-y-4">
            {jobs.map(job => (
              <JobCard
                key={job.id}
                job={job}
                onDelete={async (id) => {
                  setDeleting(id)
                  try { await training.deleteJob(id); refresh() }
                  finally { setDeleting(null) }
                }}
                onCancel={async (j) => {
                  setCancelling(j.id)
                  try { await training.cancelJob(j.id); refresh() }
                  finally { setCancelling(null) }
                }}
                deleting={deleting}
                cancelling={cancelling}
              />
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-2xl border border-border shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-5 border-b border-border flex items-center justify-between sticky top-0 bg-white z-10">
              <h2 className="text-lg font-semibold">New Training Job</h2>
              <button onClick={() => { setShowModal(false); setFormError(null) }} className="text-muted-foreground hover:text-foreground text-2xl leading-none">×</button>
            </div>

            <div className="p-6 space-y-5">
              {/* Dataset + Target */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Dataset *</label>
                  <select className="input" value={form.dataset_id} onChange={e => setForm(f => ({ ...f, dataset_id: e.target.value }))}>
                    <option value="">Select a dataset…</option>
                    {(datasetList ?? []).map(d => <option key={d.id} value={d.id}>{d.filename} (#{d.id})</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Target Column *</label>
                  <input className="input" type="text" value={form.target_column} onChange={e => setForm(f => ({ ...f, target_column: e.target.value }))} placeholder="e.g. label, target, y" />
                </div>
              </div>

              {/* Task type */}
              <div>
                <label className="label">Task Type *</label>
                <div className="grid grid-cols-2 gap-2">
                  {(['classification', 'regression'] as const).map(t => (
                    <button key={t} onClick={() => setForm(f => ({ ...f, task_type: t }))}
                      className={`px-4 py-3 rounded-xl border text-sm font-medium transition text-left ${form.task_type === t ? 'bg-foreground text-white border-foreground' : 'bg-white border-border text-foreground hover:bg-secondary'}`}>
                      <p className="font-semibold capitalize">{t}</p>
                      <p className={`text-xs mt-0.5 ${form.task_type === t ? 'text-white/70' : 'text-muted-foreground'}`}>
                        {t === 'classification' ? 'Predict a category or label' : 'Predict a continuous value'}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Algorithm */}
              <div>
                <label className="label">Algorithm *</label>
                <div className="grid grid-cols-4 gap-2">
                  {Object.entries(MODEL_PARAMS).map(([key, cfg]) => (
                    <button key={key} onClick={() => handleModelChange(key)}
                      className={`px-3 py-2 rounded-lg text-xs font-medium border transition text-left ${form.model_type === key ? 'bg-foreground text-white border-foreground' : 'bg-white border-border text-foreground hover:bg-secondary'}`}>
                      {cfg.label}
                    </button>
                  ))}
                </div>
                {modelConfig && <p className="text-xs text-muted-foreground mt-1.5">{modelConfig.description}</p>}
              </div>

              {/* Hyperparameters */}
              {modelConfig && (
                <div>
                  <button onClick={() => setShowParams(p => !p)} className="flex items-center gap-2 text-sm font-medium text-foreground mb-3 hover:text-primary transition">
                    {showParams ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    Hyperparameters
                    <span className="text-xs text-muted-foreground font-normal">(optional — defaults shown)</span>
                  </button>
                  {showParams && (
                    <div className="grid grid-cols-2 gap-4 bg-secondary/30 rounded-xl p-4">
                      {modelConfig.params.map(param => (
                        <div key={param.key}>
                          <label className="block text-xs font-medium text-foreground mb-1">{param.label}</label>
                          {param.type === 'select' ? (
                            <select className="input" style={{ padding: '5px 8px', fontSize: 12 }}
                              value={hyperparams[param.key] ?? String(param.default)}
                              onChange={e => setHyperparams(h => ({ ...h, [param.key]: e.target.value }))}>
                              {param.options?.map(o => <option key={o} value={o}>{o}</option>)}
                            </select>
                          ) : (
                            <input type="number" className="input" style={{ padding: '5px 8px', fontSize: 12 }}
                              value={hyperparams[param.key] ?? String(param.default)}
                              onChange={e => setHyperparams(h => ({ ...h, [param.key]: e.target.value }))}
                              min={param.min} max={param.max} step={param.step} />
                          )}
                          <p className="text-[10px] text-muted-foreground mt-0.5">{param.description}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {formError && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-600">
                  <AlertCircle className="w-4 h-4 shrink-0" />{formError}
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-border flex gap-3 sticky bottom-0 bg-white">
              <button onClick={() => { setShowModal(false); setFormError(null) }}
                className="flex-1 h-9 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-secondary transition">
                Cancel
              </button>
              <button onClick={handleStart} disabled={submitting}
                className="flex-1 h-9 rounded-lg bg-foreground text-white text-sm font-medium hover:bg-foreground/90 transition disabled:opacity-60">
                {submitting ? 'Starting…' : 'Start Training'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Job Card ─────────────────────────────────────────────────────────────────

function JobCard({ job, onDelete, onCancel, deleting, cancelling }: {
  job: TrainingJob
  onDelete: (id: number) => void
  onCancel: (job: TrainingJob) => void
  deleting: number | null
  cancelling: number | null
}) {
  const isClf = job.task_type === 'classification' || job.task_type == null

  return (
    <div className="bg-white border border-border rounded-xl overflow-hidden hover:border-primary/40 transition">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div>
            <p className="font-semibold text-foreground capitalize">
              {MODEL_PARAMS[job.model_type]?.label ?? job.model_type}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Job #{job.id} · Dataset #{job.dataset_id}
              {job.target_column && ` · target: ${job.target_column}`}
              {job.task_type && ` · ${job.task_type}`}
              {job.mlflow_run_id && ` · MLflow: ${job.mlflow_run_id.slice(0, 8)}`}
              {/* Guard: created_at is nullable (getattr fallback in backend) */}
              {job.created_at && ` · ${new Date(job.created_at).toLocaleDateString()}`}
            </p>
          </div>
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${statusPill(job.status)}`}>
            {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
          </span>
        </div>

        {/* Progress bar — no progress field in API, use status-based approximation */}
        <div className="h-1 bg-secondary rounded-full overflow-hidden mb-4">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: job.status === 'completed' ? '100%'
                   : job.status === 'running'   ? '60%'
                   : job.status === 'failed'    ? '100%'
                   : '10%',
              background: job.status === 'failed' ? '#ef4444' : undefined,
            }}
          />
        </div>

        {/* Metrics — classification
            roc_auc excluded: not returned by _job_to_dict() in training.py */}
        {job.status === 'completed' && isClf && (
          <div className="flex flex-wrap gap-2 mb-4">
            <MetricBadge label="Accuracy"  value={fmtPct(job.accuracy)} />
            <MetricBadge label="Precision" value={job.precision != null ? fmtPct(job.precision) : null} />
            <MetricBadge label="Recall"    value={job.recall    != null ? fmtPct(job.recall)    : null} />
            <MetricBadge label="F1"        value={job.f1_score  != null ? fmtPct(job.f1_score)  : null} />
            {job.cv_mean != null && <MetricBadge label="CV Mean" value={`${(job.cv_mean * 100).toFixed(1)}%`} />}
            {job.cv_std  != null && <MetricBadge label="CV Std"  value={`±${(job.cv_std * 100).toFixed(1)}%`} />}
          </div>
        )}

        {/* Metrics — regression */}
        {job.status === 'completed' && !isClf && (
          <div className="flex flex-wrap gap-2 mb-4">
            <MetricBadge label="R²"   value={job.r2_score != null ? job.r2_score.toFixed(4) : fmtPct(job.accuracy)} />
            <MetricBadge label="MAE"  value={job.mae  != null ? job.mae.toFixed(4)  : null} />
            <MetricBadge label="RMSE" value={job.rmse != null ? job.rmse.toFixed(4) : null} />
            {job.cv_mean != null && <MetricBadge label="CV Mean" value={job.cv_mean.toFixed(4)} />}
            {job.cv_std  != null && <MetricBadge label="CV Std"  value={`±${job.cv_std.toFixed(4)}`} />}
          </div>
        )}

        {/* Error message */}
        {job.status === 'failed' && job.error_message && (
          <div className="flex items-start gap-2 mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-200">
            <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <p className="text-xs text-red-600 font-mono break-all">{job.error_message}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2">
          {(job.status === 'running' || job.status === 'queued') && (
            <button
              onClick={() => onCancel(job)}
              disabled={cancelling === job.id}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 text-foreground transition text-xs font-medium"
            >
              <AlertCircle className="w-3.5 h-3.5" />
              {cancelling === job.id ? 'Cancelling…' : 'Cancel'}
            </button>
          )}
          <button
            onClick={() => onDelete(job.id)}
            disabled={deleting === job.id}
            className="p-1.5 rounded-lg hover:bg-red-50 text-muted-foreground hover:text-red-500 transition ml-auto"
            title={job.status === 'completed' ? 'Delete model registry entry first' : 'Delete job'}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}