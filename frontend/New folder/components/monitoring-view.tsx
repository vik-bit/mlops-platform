'use client'

import { JSXElementConstructor, Key, ReactElement, ReactNode, ReactPortal, useEffect, useState } from 'react'
import { CheckCircle, AlertCircle, Clock, Zap, BarChart3, Activity, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react'
import { useDeployments, useModels } from '@/lib/hooks'
import { monitoring, ModelStats, PredictionHistoryEntry, DriftResult } from '@/lib/api'

interface ModelCard {
  modelId: number; modelName: string; modelVersion: string
  endpoint: string; deploymentStatus: string
  metadataPath?: string
  stats: ModelStats | null; loadingStats: boolean
  history: PredictionHistoryEntry[]; loadingHistory: boolean; showHistory: boolean
  drift: DriftResult | null; loadingDrift: boolean; showDrift: boolean
}

function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: '#f8f8f6', border: '1px solid #ebebea', borderRadius: 8, padding: '12px 14px' }}>
      <p style={{ fontSize: 10, color: '#b8b8b4', textTransform: 'uppercase', letterSpacing: '.05em', fontWeight: 500, marginBottom: 4 }}>{label}</p>
      <p style={{ fontSize: 20, fontWeight: 600, color: color ?? '#111' }}>{value}</p>
    </div>
  )
}

function DriftBadge({ level }: { level: string }) {
  const map: Record<string, string> = {
    none:     'text-green-700 bg-green-50 border border-green-200',
    moderate: 'text-amber-600 bg-amber-50 border border-amber-200',
    high:     'text-red-600 bg-red-50 border border-red-200',
    unknown:  'text-gray-500 bg-gray-50 border border-gray-200',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${map[level] ?? map.unknown}`}>
      {level.charAt(0).toUpperCase() + level.slice(1)}
    </span>
  )
}

export default function MonitoringView() {
  const { data: deploymentList, loading: deploymentsLoading } = useDeployments()
  const { data: modelList } = useModels()
  const [modelCards, setModelCards] = useState<ModelCard[]>([])

  useEffect(() => {
    if (!deploymentList || deploymentList.length === 0) return
    const cards: ModelCard[] = deploymentList.map(dep => {
      const model = (modelList ?? []).find(m => m.id === dep.model_id)
      return {
        modelId: dep.model_id, modelName: model?.model_name ?? `Model #${dep.model_id}`,
        modelVersion: model?.model_version ?? '—', endpoint: dep.endpoint,
        deploymentStatus: dep.status, stats: null, loadingStats: true,
        history: [], loadingHistory: false, showHistory: false,
        drift: null, loadingDrift: false, showDrift: false,
      }
    })
    setModelCards(cards)
    cards.forEach((card, i) => {
      monitoring.modelStats(card.modelId)
        .then(stats => setModelCards(prev => prev.map((c, idx) => idx === i ? { ...c, stats, loadingStats: false } : c)))
        .catch(() => setModelCards(prev => prev.map((c, idx) => idx === i ? { ...c, loadingStats: false } : c)))
    })
  }, [deploymentList, modelList])

  const toggleHistory = async (modelId: number, index: number) => {
    const card = modelCards[index]
    if (card.showHistory) {
      setModelCards(prev => prev.map((c, i) => i === index ? { ...c, showHistory: false } : c)); return
    }
    setModelCards(prev => prev.map((c, i) => i === index ? { ...c, showHistory: true, loadingHistory: true } : c))
    try {
      const history = await monitoring.predictionHistory(modelId, 20)
      setModelCards(prev => prev.map((c, i) => i === index ? { ...c, history, loadingHistory: false } : c))
    } catch {
      setModelCards(prev => prev.map((c, i) => i === index ? { ...c, loadingHistory: false } : c))
    }
  }

  const toggleDrift = async (modelId: number, index: number) => {
    const card = modelCards[index]
    if (card.showDrift) {
      setModelCards(prev => prev.map((c, i) => i === index ? { ...c, showDrift: false } : c)); return
    }
    // metadata_path is now typed on ModelVersion — no cast needed
    const model = (modelList ?? []).find(m => m.id === modelId)
    const metaPath = model?.metadata_path
    if (!metaPath) {
      setModelCards(prev => prev.map((c, i) => i === index ? {
        ...c, showDrift: true, drift: { model_id: modelId, logs_analysed: 0, parse_errors: 0,
          window: 500, overall_psi: null, overall_drift: 'unknown', drifted_features: [],
          needs_retraining: false, features: {},
          // @ts-ignore
          error: 'No metadata found for this model. Retrain to generate a drift baseline.' }
      } : c)); return
    }
    setModelCards(prev => prev.map((c, i) => i === index ? { ...c, showDrift: true, loadingDrift: true } : c))
    try {
      const drift = await monitoring.drift(modelId, metaPath)
      setModelCards(prev => prev.map((c, i) => i === index ? { ...c, drift, loadingDrift: false } : c))
    } catch (err) {
      setModelCards(prev => prev.map((c, i) => i === index ? { ...c, loadingDrift: false,
        drift: { model_id: modelId, logs_analysed: 0, parse_errors: 0, window: 500,
          overall_psi: null, overall_drift: 'unknown', drifted_features: [],
          // @ts-ignore
          needs_retraining: false, features: {}, error: err instanceof Error ? err.message : 'Drift check failed' } } : c))
    }
  }

  const totalPredictions = modelCards.reduce((s, c) => s + (c.stats?.total_predictions ?? 0), 0)
  const avgLatency = (() => {
    const w = modelCards.filter(c => c.stats?.avg_latency_ms != null)
    return w.length ? w.reduce((s, c) => s + c.stats!.avg_latency_ms, 0) / w.length : null
  })()
  const avgSuccessRate = (() => {
    const w = modelCards.filter(c => c.stats?.success_rate != null)
    return w.length ? w.reduce((s, c) => s + c.stats!.success_rate, 0) / w.length : null
  })()
  const activeCount = deploymentList?.filter(d => d.status === 'active').length ?? 0

  return (
    <div className="flex-1 overflow-auto bg-white">
      <div className="border-b border-border bg-white sticky top-0 z-10">
        <div className="px-8 py-6">
          <h1 className="text-3xl font-bold text-foreground">Monitoring</h1>
          <p className="text-muted-foreground mt-1">Live stats, prediction history, and drift detection</p>
        </div>
      </div>

      <div className="p-8">
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="bg-white border border-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3"><Zap className="w-4 h-4 text-green-500" /><p className="text-sm text-muted-foreground">Active Models</p></div>
            <p className="text-3xl font-bold text-foreground">{activeCount}</p>
          </div>
          <div className="bg-white border border-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3"><BarChart3 className="w-4 h-4 text-blue-500" /><p className="text-sm text-muted-foreground">Total Predictions</p></div>
            <p className="text-3xl font-bold text-foreground">{deploymentsLoading ? '…' : totalPredictions.toLocaleString()}</p>
          </div>
          <div className="bg-white border border-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3"><Clock className="w-4 h-4 text-amber-500" /><p className="text-sm text-muted-foreground">Avg Latency</p></div>
            <p className="text-3xl font-bold text-foreground">{avgLatency != null ? `${avgLatency.toFixed(0)}ms` : '—'}</p>
          </div>
          <div className="bg-white border border-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3"><Activity className="w-4 h-4 text-purple-500" /><p className="text-sm text-muted-foreground">Success Rate</p></div>
            <p className="text-3xl font-bold text-foreground">{avgSuccessRate != null ? `${avgSuccessRate.toFixed(1)}%` : '—'}</p>
          </div>
        </div>

        {deploymentsLoading ? (
          <div className="space-y-4">{[1,2].map(i => <div key={i} className="h-48 bg-secondary rounded-xl animate-pulse" />)}</div>
        ) : modelCards.length === 0 ? (
          <div className="text-center py-20 border border-dashed border-border rounded-xl">
            <BarChart3 className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-medium text-foreground mb-1">No deployed models yet</p>
            <p className="text-sm text-muted-foreground">Deploy a model to start seeing performance metrics</p>
          </div>
        ) : (
          <div className="space-y-4">
            {modelCards.map((card, i) => (
              <div key={card.modelId} className="bg-white border border-border rounded-xl overflow-hidden">
                <div className="p-6">
                  <div className="flex items-start justify-between mb-5">
                    <div>
                      <h3 className="text-base font-semibold text-foreground">{card.modelName}</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">Version {card.modelVersion} · Model #{card.modelId}</p>
                      <p className="text-xs text-muted-foreground font-mono mt-0.5 truncate max-w-sm">{card.endpoint}</p>
                    </div>
                    <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${card.deploymentStatus === 'active' ? 'text-green-700 bg-green-50 border border-green-200' : 'text-gray-400 bg-gray-50 border border-gray-200'}`}>
                      {card.deploymentStatus === 'active' ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                      {card.deploymentStatus}
                    </span>
                  </div>

                  {card.loadingStats ? (
                    <div className="grid grid-cols-5 gap-3">{[1,2,3,4,5].map(j => <div key={j} className="h-16 bg-secondary rounded-lg animate-pulse" />)}</div>
                  ) : card.stats ? (
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                      <StatBox label="Predictions"  value={card.stats.total_predictions.toLocaleString()} />
                      <StatBox label="Avg Latency"  value={`${card.stats.avg_latency_ms.toFixed(0)}ms`} />
                      <StatBox label="Success Rate" value={`${card.stats.success_rate.toFixed(1)}%`} color={card.stats.success_rate >= 95 ? '#16a34a' : card.stats.success_rate >= 80 ? '#d97706' : '#dc2626'} />
                      <StatBox label="Successful"   value={card.stats.successful_requests.toLocaleString()} color="#16a34a" />
                      <StatBox label="Failed"       value={card.stats.failed_requests.toLocaleString()} color={card.stats.failed_requests > 0 ? '#dc2626' : '#111'} />
                    </div>
                  ) : <p className="text-sm text-muted-foreground">No prediction data yet</p>}

                  {card.stats?.last_prediction_time && (
                    <p className="text-xs text-muted-foreground mt-3">Last prediction: {new Date(card.stats.last_prediction_time).toLocaleString()}</p>
                  )}

                  <div className="flex items-center gap-3 mt-4">
                    <button onClick={() => toggleHistory(card.modelId, i)} className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition">
                      {card.showHistory ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      {card.showHistory ? 'Hide' : 'Show'} history
                    </button>
                    <button onClick={() => toggleDrift(card.modelId, i)} className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      {card.showDrift ? 'Hide' : 'Check'} drift
                    </button>
                  </div>
                </div>

                {/* History */}
                {card.showHistory && (
                  <div style={{ borderTop: '1px solid #ebebea' }}>
                    {card.loadingHistory ? (
                      <div className="p-4 text-center text-sm text-muted-foreground">Loading history…</div>
                    ) : card.history.length === 0 ? (
                      <div className="p-4 text-center text-sm text-muted-foreground">No predictions recorded yet</div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="data-table" style={{ margin: 0 }}>
                          <thead>
                            <tr style={{ background: '#fafaf8' }}>
                              <th style={{ padding: '10px 16px' }}>ID</th>
                              <th style={{ padding: '10px 16px' }}>Prediction</th>
                              <th style={{ padding: '10px 16px' }}>Latency</th>
                              <th style={{ padding: '10px 16px' }}>Status</th>
                              <th style={{ padding: '10px 16px' }}>Time</th>
                            </tr>
                          </thead>
                          <tbody>
                            {card.history.map(h => (
                              <tr key={h.id}>
                                <td style={{ padding: '8px 16px', fontFamily: 'monospace', fontSize: 11, color: '#b8b8b4' }}>#{h.id}</td>
                                <td style={{ padding: '8px 16px', fontWeight: 500, color: '#111' }}>{h.prediction}</td>
                                <td style={{ padding: '8px 16px' }}>{h.latency_ms?.toFixed(1)}ms</td>
                                <td style={{ padding: '8px 16px' }}>
                                  <span className={`pill ${h.status === 'success' ? 'pill-green' : 'pill-red'}`}>{h.status}</span>
                                </td>
                                <td style={{ padding: '8px 16px', fontSize: 11 }}>{new Date(h.created_at).toLocaleString()}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Drift */}
                {card.showDrift && (
                  <div style={{ borderTop: '1px solid #ebebea' }}>
                    <div className="p-6">
                      {card.loadingDrift ? (
                        <p className="text-sm text-muted-foreground">Analysing drift…</p>
                      ) : card.drift ? (
                        <>
                          {(card.drift as any).error ? (
                            <p className="text-sm text-amber-600">{(card.drift as any).error}</p>
                          ) : (
                            <>
                              <div className="flex items-center gap-4 mb-4 flex-wrap">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm text-muted-foreground">Overall drift:</span>
                                  <DriftBadge level={card.drift.overall_drift} />
                                </div>
                                {card.drift.overall_psi != null && (
                                  <span className="text-sm text-muted-foreground">PSI: <b className="text-foreground">{card.drift.overall_psi.toFixed(4)}</b></span>
                                )}
                                <span className="text-sm text-muted-foreground">Logs: <b className="text-foreground">{card.drift.logs_analysed}</b></span>
                                {card.drift.needs_retraining && (
                                  <span className="flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded">
                                    <AlertTriangle className="w-3 h-3" /> Retrain recommended
                                  </span>
                                )}
                              </div>

                              {card.drift.drifted_features.length > 0 && (
                                <div className="mb-4">
                                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Drifted Features</p>
                                  <div className="flex flex-wrap gap-1.5">
                                    {card.drift.drifted_features.map((f: any) => (
                                      <span key={f} className="text-xs px-2 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-700">{f}</span>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {Object.entries(card.drift.features).length > 0 && (
                                <div className="overflow-x-auto">
                                  <table className="data-table text-xs">
                                    <thead>
                                      <tr>
                                        <th>Feature</th><th>Type</th><th>PSI</th><th>Drift</th><th>Samples</th><th>Current Mean</th><th>Baseline Mean</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {Object.entries(card.drift.features as Record<string, { type?: string; psi?: number; drift_level?: string; status?: string; samples?: number; current_mean?: number; baseline_mean?: number }>).map(([feat, info]) => (
                                        <tr key={feat}>
                                          <td style={{ fontWeight: 500, color: '#111' }}>{feat}</td>
                                          <td>{info.type ?? '—'}</td>
                                          <td>{info.psi?.toFixed(4) ?? '—'}</td>
                                          <td>{info.drift_level ? <DriftBadge level={info.drift_level} /> : info.status ?? '—'}</td>
                                          <td>{info.samples}</td>
                                          <td>{info.current_mean?.toFixed(3) ?? '—'}</td>
                                          <td>{info.baseline_mean?.toFixed(3) ?? '—'}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              )}
                            </>
                          )}
                        </>
                      ) : null}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}