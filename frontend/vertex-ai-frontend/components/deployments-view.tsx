'use client'

import { useState } from 'react'
import { Plus, Zap, Trash2, Copy, CheckCircle, AlertCircle, Terminal, UploadCloud, Lightbulb } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDeployments, useModels } from '@/lib/hooks'
import { deployments as deploymentsApi, ModelSchema, ShapExplanation } from '@/lib/api'

export default function DeploymentsView() {
  const { data, loading, refresh } = useDeployments()
  const deploymentList = data ?? []
  const { data: modelList } = useModels()

  const [showModal, setShowModal]         = useState(false)
  const [selectedModelId, setSelectedModelId] = useState('')
  const [deploying, setDeploying]         = useState(false)
  const [deployError, setDeployError]     = useState<string | null>(null)
  const [undeploying, setUndeploying]     = useState<number | null>(null)
  const [copied, setCopied]               = useState<string | null>(null)

  // Per-deployment expanded panels
  const [expandedId, setExpandedId]       = useState<number | null>(null)
  const [schemas, setSchemas]             = useState<Record<number, ModelSchema | null>>({})
  const [loadingSchema, setLoadingSchema] = useState<number | null>(null)
  const [shapResult, setShapResult]       = useState<Record<number, ShapExplanation | null>>({})
  const [loadingShap, setLoadingShap]     = useState<number | null>(null)
  const [predictInputs, setPredictInputs] = useState<Record<number, Record<string, string>>>({})
  const [predictResults, setPredictResults] = useState<Record<number, string | null>>({})
  const [predicting, setPredicting]       = useState<number | null>(null)
  const [batchFile, setBatchFile]         = useState<Record<number, File | null>>({})
  const [batchRunning, setBatchRunning]   = useState<number | null>(null)

  const handleDeploy = async () => {
    if (!selectedModelId) { setDeployError('Select a model'); return }
    setDeploying(true); setDeployError(null)
    try {
      await deploymentsApi.deploy(parseInt(selectedModelId))
      setShowModal(false); setSelectedModelId(''); refresh()
    } catch (err: unknown) {
      setDeployError(err instanceof Error ? err.message : 'Deploy failed')
    } finally { setDeploying(false) }
  }

  const handleUndeploy = async (id: number) => {
    setUndeploying(id)
    try { await deploymentsApi.undeploy(id); refresh() } catch {}
    finally { setUndeploying(null) }
  }

  const copyEndpoint = (endpoint: string) => {
    const full = `${process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'}${endpoint}`
    navigator.clipboard.writeText(full)
    setCopied(endpoint); setTimeout(() => setCopied(null), 2000)
  }

  const loadSchema = async (modelId: number) => {
    if (schemas[modelId] !== undefined) return
    setLoadingSchema(modelId)
    try {
      const s = await deploymentsApi.schema(modelId)
      setSchemas(prev => ({ ...prev, [modelId]: s }))
      // Initialise inputs with empty strings
      const init: Record<string, string> = {}
      Object.keys(s.features).forEach(f => { init[f] = '' })
      setPredictInputs(prev => ({ ...prev, [modelId]: init }))
    } catch {
      setSchemas(prev => ({ ...prev, [modelId]: null }))
    } finally { setLoadingSchema(null) }
  }

  const toggleExpand = (depId: number, modelId: number) => {
    if (expandedId === depId) { setExpandedId(null); return }
    setExpandedId(depId)
    loadSchema(modelId)
  }

  const handlePredict = async (modelId: number) => {
    const schema = schemas[modelId]
    if (!schema) return
    const features: Record<string, unknown> = {}
    Object.entries(predictInputs[modelId] ?? {}).forEach(([k, v]) => {
      if (schema.features[k] === 'numeric') {
        const n = parseFloat(v)
        features[k] = isNaN(n) ? 0 : n
      } else {
        features[k] = v || ''
      }
    })
    setPredicting(modelId)
    try {
      const res = await deploymentsApi.predictNamed(modelId, features)
      setPredictResults(prev => ({
        ...prev,
        [modelId]: `Prediction: ${res.prediction}${res.probability
          ? `\nProbabilities: ${Object.entries(res.probability).map(([k, v]) => `${k}: ${(v * 100).toFixed(1)}%`).join(', ')}`
          : ''}${res.latency_ms ? `\nLatency: ${res.latency_ms.toFixed(1)}ms` : ''}`
      }))
    } catch (err: unknown) {
      setPredictResults(prev => ({ ...prev, [modelId]: `Error: ${err instanceof Error ? err.message : 'Prediction failed'}` }))
    } finally { setPredicting(null) }
  }

  const handleExplain = async (modelId: number) => {
    const schema = schemas[modelId]
    if (!schema) return
    const features: Record<string, unknown> = {}
    Object.entries(predictInputs[modelId] ?? {}).forEach(([k, v]) => {
      if (schema.features[k] === 'numeric') {
        const n = parseFloat(v)
        features[k] = isNaN(n) ? 0 : n
      } else {
        features[k] = v || ''
      }
    })
    setLoadingShap(modelId)
    try {
      const res = await deploymentsApi.explain(modelId, features)
      // Log raw response so we can see exactly what the backend returned
      console.log('[SHAP] raw response:', JSON.stringify(res))

      // Normalize — backend slow path omits model_id/source/prediction at top level
      const normalized: ShapExplanation = {
        model_id:          (res as any).model_id          ?? modelId,
        prediction:        (res as any).prediction        ?? '?',
        global_importance: (res as any).global_importance ?? null,
        local_explanation: (res as any).local_explanation ?? null,
        base_value:        (res as any).base_value        ?? null,
        source:            (res as any).source            ?? 'realtime',
        error:             (res as any).error             ?? undefined,
      }
      setShapResult(prev => ({ ...prev, [modelId]: normalized }))
    } catch (err: unknown) {
      console.error('[SHAP] request failed:', err)
      setShapResult(prev => ({ ...prev, [modelId]: {
        model_id: modelId, prediction: '?',
        global_importance: null, local_explanation: null,
        base_value: null, source: 'realtime' as const,
        error: err instanceof Error ? err.message : 'SHAP request failed',
      }}))
    } finally { setLoadingShap(null) }
  }

  const handleBatchPredict = async (modelId: number) => {
    const file = batchFile[modelId]
    if (!file) return
    setBatchRunning(modelId)
    try {
      const url = await deploymentsApi.predictBatch(modelId, file)
      const a = document.createElement('a')
      a.href = url; a.download = `predictions_model_${modelId}.csv`; a.click()
      URL.revokeObjectURL(url)
    } catch (err: unknown) {
      alert(`Batch failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally { setBatchRunning(null) }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':   return 'text-green-600 bg-green-100'
      case 'stopped':  return 'text-gray-400 bg-gray-500/20'
      case 'error':    return 'text-red-600 bg-red-100'
      default:         return 'text-gray-400 bg-gray-500/20'
    }
  }

  const activeCount = deploymentList.filter(d => d.status === 'active').length

  return (
    <div className="flex-1 overflow-auto bg-white">
      <div className="border-b border-border bg-white/40 sticky top-0 z-10">
        <div className="px-8 py-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Deployments</h1>
            <p className="text-muted-foreground mt-1">Manage and monitor your deployed models</p>
          </div>
          <Button className="bg-primary hover:bg-primary/90 text-primary-foreground" onClick={() => setShowModal(true)}>
            <Plus className="w-4 h-4 mr-2" />Deploy Model
          </Button>
        </div>
      </div>

      <div className="p-8">
        {loading ? (
          <div className="space-y-4 mb-8">{[1,2].map(i => <div key={i} className="h-48 bg-secondary rounded-xl animate-pulse" />)}</div>
        ) : deploymentList.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground border border-dashed border-border rounded-xl mb-8">
            <p className="text-lg font-medium mb-2">No deployments yet</p>
            <p className="text-sm">Deploy a trained model to get started</p>
          </div>
        ) : (
          <div className="space-y-6 mb-8">
            {deploymentList.map((dep) => {
              const schema = schemas[dep.model_id]
              const isExpanded = expandedId === dep.id
              const shap = shapResult[dep.model_id]

              return (
                <div key={dep.id} className="bg-white border border-border rounded-xl overflow-hidden hover:border-primary/50 transition">
                  <div className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-xl font-semibold text-foreground">Model #{dep.model_id}</h3>
                        <p className="text-sm text-muted-foreground">Deployment #{dep.id}</p>
                      </div>
                      <div className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 ${getStatusColor(dep.status)}`}>
                        {dep.status === 'active' ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                        {dep.status.charAt(0).toUpperCase() + dep.status.slice(1)}
                      </div>
                    </div>

                    <div className="mb-4 p-3 bg-secondary/40 rounded-lg">
                      <p className="text-xs text-muted-foreground mb-1">API Endpoint</p>
                      <div className="flex items-center gap-2">
                        <code className="text-sm text-accent flex-1 truncate font-mono">{dep.endpoint}</code>
                        <button onClick={() => copyEndpoint(dep.endpoint)} className="p-1.5 hover:bg-white rounded transition text-muted-foreground hover:text-foreground">
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        {copied === dep.endpoint && <span className="text-xs text-green-500">Copied!</span>}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => toggleExpand(dep.id, dep.model_id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-secondary transition text-foreground"
                      >
                        <Terminal className="w-3.5 h-3.5" />
                        {isExpanded ? 'Hide' : 'Predict / Explain'}
                      </button>
                      <button
                        onClick={() => handleUndeploy(dep.id)}
                        disabled={undeploying === dep.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-red-50 text-muted-foreground hover:text-red-500 transition border border-border ml-auto"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        {undeploying === dep.id ? 'Removing…' : 'Undeploy'}
                      </button>
                    </div>
                  </div>

                  {/* Expanded prediction panel */}
                  {isExpanded && (
                    <div style={{ borderTop: '1px solid #ebebea' }}>
                      <div className="p-6 space-y-6">
                        {loadingSchema === dep.model_id ? (
                          <p className="text-sm text-muted-foreground">Loading model schema…</p>
                        ) : schema === null ? (
                          <p className="text-sm text-red-500">Could not load model schema</p>
                        ) : schema ? (
                          <>
                            {/* Model info */}
                            <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
                              {schema.model_type && <span>Model: <b className="text-foreground">{schema.model_type}</b></span>}
                              {schema.task_type  && <span>Task: <b className="text-foreground capitalize">{schema.task_type}</b></span>}
                              <span>Features: <b className="text-foreground">{Object.keys(schema.features).length}</b></span>
                            </div>

                            {/* Feature inputs */}
                            <div>
                              <p className="text-sm font-semibold text-foreground mb-3">Online Prediction</p>
                              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-4">
                                {Object.entries(schema.features).map(([feat, type]) => (
                                  <div key={feat}>
                                    <label className="block text-xs text-muted-foreground mb-1 truncate" title={feat}>
                                      {feat} <span className="text-muted-foreground/60">({type})</span>
                                    </label>
                                    <input
                                      type={type === 'numeric' ? 'number' : 'text'}
                                      className="input w-full"
                                      style={{ padding: '5px 8px', fontSize: 12 }}
                                      placeholder={type === 'numeric' ? '0.0' : 'value'}
                                      value={predictInputs[dep.model_id]?.[feat] ?? ''}
                                      onChange={e => setPredictInputs(prev => ({
                                        ...prev,
                                        [dep.model_id]: { ...prev[dep.model_id], [feat]: e.target.value }
                                      }))}
                                    />
                                  </div>
                                ))}
                              </div>

                              <div className="flex gap-2 mb-4">
                                <button
                                  onClick={() => handlePredict(dep.model_id)}
                                  disabled={predicting === dep.model_id}
                                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-foreground text-white text-xs font-medium hover:bg-foreground/90 transition disabled:opacity-60"
                                >
                                  <Zap className="w-3.5 h-3.5" />
                                  {predicting === dep.model_id ? 'Predicting…' : 'Predict'}
                                </button>
                                <button
                                  onClick={() => handleExplain(dep.model_id)}
                                  disabled={loadingShap === dep.model_id}
                                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-border text-xs font-medium hover:bg-secondary transition disabled:opacity-60"
                                >
                                  <Lightbulb className="w-3.5 h-3.5" />
                                  {loadingShap === dep.model_id ? 'Computing SHAP…' : 'Explain'}
                                </button>
                              </div>

                              {predictResults[dep.model_id] && (
                                <pre className="text-xs bg-secondary/40 rounded-lg p-3 font-mono whitespace-pre-wrap border border-border text-foreground">
                                  {predictResults[dep.model_id]}
                                </pre>
                              )}
                            </div>

                            {/* SHAP explanation */}
                            {shap && (
                              <>
                                <div>
                                  <p className="text-sm font-semibold text-foreground mb-3">
                                    SHAP Explanation
                                    {shap.source && <span className="text-xs text-muted-foreground font-normal ml-2">({shap.source})</span>}
                                  </p>
                                  {shap.error ? (
                                    <p className="text-xs text-red-500 font-mono break-all">{shap.error}</p>
                                  ) : shap.global_importance && Object.keys(shap.global_importance).length > 0 ? (
                                    <div className="space-y-1.5">
                                      {Object.entries(shap.global_importance).slice(0, 10).map(([feat, imp]) => {
                                        const max = Math.max(...Object.values(shap.global_importance!))
                                        const pct = max > 0 ? (imp / max) * 100 : 0
                                        return (
                                          <div key={feat} className="flex items-center gap-2">
                                            <span className="text-xs text-muted-foreground w-32 truncate text-right flex-shrink-0" title={feat}>{feat}</span>
                                            <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
                                              <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
                                            </div>
                                            <span className="text-xs font-mono text-foreground w-14 text-right">{(imp as number).toFixed(4)}</span>
                                          </div>
                                        )
                                      })}
                                    </div>
                                  ) : (
                                    <p className="text-xs text-amber-500">
                                      No feature importance data returned. Check browser console for the raw response — look for <code>[SHAP] raw response</code>.
                                    </p>
                                  )}
                                </div>

                                {shap.base_value !== null && (
                                  <div className="mb-4 p-3 rounded-lg bg-secondary/40 border border-border">
                                    <p className="text-xs text-muted-foreground">
                                      Base Value
                                    </p>

                                    <p className="text-lg font-semibold text-foreground">
                                      {typeof shap.base_value === 'number'
                                        ? shap.base_value.toFixed(4)
                                        : shap.base_value}
                                    </p>

                                    <p className="text-xs text-muted-foreground mt-1">
                                      Model prediction before feature contributions are applied.
                                    </p>
                                  </div>
                                )}

                                {/* Local Explanation */}
                                {shap.local_explanation && shap.local_explanation.length > 0 && (
                                  <div className="mt-6">
                                    <p className="text-sm font-semibold text-foreground mb-3">
                                      Local Feature Contributions
                                    </p>

                                    <div className="space-y-2">
                                      {shap.local_explanation
                                        .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
                                        .map((item) => (
                                          <div
                                            key={item.feature}
                                            className="flex items-center gap-3 p-2 rounded-lg border border-border"
                                          >
                                            <div className="flex-1 min-w-0">
                                              <p
                                                className="text-xs font-medium truncate"
                                                title={item.feature}
                                              >
                                                {item.feature}
                                              </p>

                                              <p className="text-[11px] text-muted-foreground">
                                                Value: {String(item.value)}
                                              </p>
                                            </div>

                                            <span
                                              className={`text-xs font-semibold ${
                                                item.shap_value >= 0
                                                  ? 'text-green-600'
                                                  : 'text-red-600'
                                              }`}
                                            >
                                              {item.shap_value >= 0 ? '+' : ''}
                                              {item.shap_value.toFixed(4)}
                                            </span>
                                          </div>
                                        ))}
                                    </div>
                                  </div>
                                )}
                              </>
                            )}
                            {/* Batch prediction */}
                            <div>
                              <p className="text-sm font-semibold text-foreground mb-2">Batch Prediction</p>
                              <p className="text-xs text-muted-foreground mb-3">Upload a CSV with the same feature columns — download comes back with a <code>prediction</code> column appended.</p>
                              <div className="flex items-center gap-3">
                                <input
                                  type="file"
                                  accept=".csv"
                                  className="text-xs text-muted-foreground"
                                  onChange={e => setBatchFile(prev => ({ ...prev, [dep.model_id]: e.target.files?.[0] ?? null }))}
                                />
                                <button
                                  onClick={() => handleBatchPredict(dep.model_id)}
                                  disabled={!batchFile[dep.model_id] || batchRunning === dep.model_id}
                                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-foreground text-white text-xs font-medium hover:bg-foreground/90 transition disabled:opacity-50"
                                >
                                  <UploadCloud className="w-3.5 h-3.5" />
                                  {batchRunning === dep.model_id ? 'Running…' : 'Run & Download'}
                                </button>
                              </div>
                            </div>
                          </>
                        ) : null}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white border border-border rounded-xl p-6">
            <p className="text-muted-foreground text-sm mb-2">Active Models</p>
            <p className="text-3xl font-bold text-green-400">{activeCount}</p>
          </div>
          <div className="bg-white border border-border rounded-xl p-6">
            <p className="text-muted-foreground text-sm mb-2">Total Deployments</p>
            <p className="text-3xl font-bold text-foreground">{deploymentList.length}</p>
          </div>
          <div className="bg-white border border-border rounded-xl p-6">
            <p className="text-muted-foreground text-sm mb-2">Available Models</p>
            <p className="text-3xl font-bold text-foreground">{(modelList ?? []).length}</p>
          </div>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl border border-border shadow-2xl w-full max-w-md p-6">
            <h2 className="text-xl font-semibold text-foreground mb-6">Deploy Model</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-1.5">Model *</label>
                <select
                  value={selectedModelId}
                  onChange={e => setSelectedModelId(e.target.value)}
                  className="w-full h-9 px-3 bg-secondary border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-primary/50"
                >
                  <option value="">Select a model…</option>
                  {(modelList ?? []).map(m => (
                    <option key={m.id} value={m.id}>
                      {m.model_name} v{m.model_version} (#{m.id})
                      {m.accuracy ? ` · ${(parseFloat(m.accuracy) * 100).toFixed(1)}% score` : ''}
                      {` · ${m.stage}`}
                    </option>
                  ))}
                </select>
              </div>
              {deployError && <p className="text-sm text-destructive">{deployError}</p>}
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => { setShowModal(false); setDeployError(null) }}
                className="flex-1 h-9 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-secondary transition"
              >Cancel</button>
              <button
                onClick={handleDeploy}
                disabled={deploying}
                className="flex-1 h-9 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition disabled:opacity-60"
              >{deploying ? 'Deploying…' : 'Deploy'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}