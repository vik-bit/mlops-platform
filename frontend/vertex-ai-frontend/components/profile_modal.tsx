'use client'

import { useState } from 'react'
import { X, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { DatasetProfile } from '@/lib/api'

interface ProfileModalProps {
  open: boolean
  onClose: () => void
  profile: DatasetProfile | null
  datasetName: string
  onTargetChange: (target: string) => void
  selectedTarget: string
  onReloadProfile: () => void
  loading?: boolean
}

const getTopCorrelations = (
  matrix: Record<string, Record<string, number>>
) => {
  const pairs: { featureA: string; featureB: string; correlation: number }[] = []

  Object.entries(matrix).forEach(([featureA, values]) => {
    Object.entries(values).forEach(([featureB, corr]) => {
      if (featureA !== featureB && featureA < featureB) {
        pairs.push({
          featureA,
          featureB,
          correlation: Math.abs(corr),
        })
      }
    })
  })

  return pairs
    .sort((a, b) => b.correlation - a.correlation)
    .slice(0, 10)
}

export default function ProfileModal({
  open,
  onClose,
  profile,
  datasetName,
  onTargetChange,
  selectedTarget,
  onReloadProfile,
  loading,
}: ProfileModalProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-xl max-w-6xl w-full max-h-[90vh] overflow-y-auto my-8">
        {/* Header */}
        <div className="sticky top-0 border-b border-border bg-white px-8 py-6 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-foreground">{datasetName}</h2>
            <p className="text-sm text-muted-foreground mt-1">Dataset Profile & Analysis</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-secondary rounded-lg transition"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Content */}
        <div className="px-8 py-6">
          {loading ? (
            <div className="text-center py-12">
              <p className="text-muted-foreground">Loading profile…</p>
            </div>
          ) : profile ? (
            <div className="space-y-8">
              {/* Target Selection */}
              <div className="flex items-end gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Target Column
                  </label>
                  <select
                    className="w-full border border-border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                    value={selectedTarget}
                    onChange={(e) => onTargetChange(e.target.value)}
                  >
                    <option value="">Select target variable</option>
                    {profile.columns &&
                      Object.keys(profile.columns).map((col) => (
                        <option key={col} value={col}>
                          {col}
                        </option>
                      ))}
                  </select>
                </div>
                <Button
                  onClick={onReloadProfile}
                  disabled={!selectedTarget}
                  className="px-6"
                >
                  Reload Analysis
                </Button>
              </div>

              {/* Overview Stats */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-foreground">Overview</h3>
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-secondary/50 border border-border rounded-lg p-4">
                    <p className="text-xs text-muted-foreground mb-1">Rows</p>
                    <p className="text-lg font-bold text-foreground">
                      {profile.row_count?.toLocaleString()}
                    </p>
                  </div>
                  <div className="bg-secondary/50 border border-border rounded-lg p-4">
                    <p className="text-xs text-muted-foreground mb-1">Columns</p>
                    <p className="text-lg font-bold text-foreground">
                      {profile.column_count}
                    </p>
                  </div>
                  <div className="bg-secondary/50 border border-border rounded-lg p-4">
                    <p className="text-xs text-muted-foreground mb-1">Missing %</p>
                    <p className="text-lg font-bold text-foreground">
                      {profile.missing_pct ?? 0}%
                    </p>
                  </div>
                  <div className="bg-secondary/50 border border-border rounded-lg p-4">
                    <p className="text-xs text-muted-foreground mb-1">Duplicate Rows</p>
                    <p className="text-lg font-bold text-foreground">0</p>
                  </div>
                </div>
              </div>

              {/* Warnings */}
              {profile.warnings && profile.warnings.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground">Dataset Warnings</h3>
                  <div className="space-y-2">
                    {profile.warnings.map((warning, idx) => (
                      <div
                        key={idx}
                        className="bg-amber-50 border border-amber-200 text-amber-700 rounded-lg p-3 text-sm flex items-start gap-2"
                      >
                        <span className="text-lg">⚠</span>
                        <span>{warning}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Target Analysis */}
              {profile.target && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground">Target Analysis</h3>
                  <div className="grid grid-cols-4 gap-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <p className="text-xs text-blue-600 mb-1">Target Column</p>
                      <p className="font-medium text-foreground">{profile.target.column}</p>
                    </div>
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <p className="text-xs text-blue-600 mb-1">Data Type</p>
                      <p className="font-medium text-foreground">{profile.target.dtype}</p>
                    </div>
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <p className="text-xs text-blue-600 mb-1">Suggested Task</p>
                      <p className="font-medium text-foreground">
                        {profile.target.suggested_task}
                      </p>
                    </div>
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <p className="text-xs text-blue-600 mb-1">Classes</p>
                      <p className="font-medium text-foreground">{profile.target.n_unique}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Feature Importance */}
              {profile.feature_rankings && profile.feature_rankings.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground">Feature Importance</h3>
                  <div className="border border-border rounded-lg p-4 bg-secondary/30">
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={profile.feature_rankings}>
                        <XAxis dataKey="feature" angle={-45} textAnchor="end" height={80} />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="score" fill="#3b82f6" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Outliers */}
              {profile.outliers && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground">Outliers</h3>
                  <div className="border border-border rounded-lg p-4 bg-secondary/30">
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart
                        data={Object.entries(profile.outliers).map(([feature, count]) => ({
                          feature,
                          count,
                        }))}
                      >
                        <XAxis dataKey="feature" angle={-45} textAnchor="end" height={80} />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="count" fill="#ef4444" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Distributions */}
              {profile.distributions &&
                Object.entries(profile.distributions).map(([column, dist]) => (
                  <div key={column} className="space-y-3">
                    <h3 className="text-sm font-semibold text-foreground">
                      Distribution: {column}
                    </h3>
                    <div className="border border-border rounded-lg p-4 bg-secondary/30">
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart
                          data={dist.bins.map((bin, index) => ({
                            bin,
                            count: dist.counts[index],
                          }))}
                        >
                          <XAxis dataKey="bin" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="count" fill="#10b981" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                ))}

              {/* Correlations */}
              {profile.correlation_matrix && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground">Strongest Correlations</h3>
                  <div className="border border-border rounded-lg p-4 bg-secondary/30">
                    <ResponsiveContainer width="100%" height={350}>
                      <BarChart
                        layout="vertical"
                        data={getTopCorrelations(profile.correlation_matrix).map((item) => ({
                          feature: `${item.featureA} ↔ ${item.featureB}`,
                          correlation: Number(item.correlation.toFixed(3)),
                        }))}
                      >
                        <XAxis type="number" />
                        <YAxis type="category" dataKey="feature" width={220} />
                        <Tooltip />
                        <Bar dataKey="correlation" fill="#8b5cf6" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Feature Engineering */}
              {profile.feature_engineering && profile.feature_engineering.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground">Feature Engineering</h3>
                  <div className="space-y-2">
                    {profile.feature_engineering.map((fe) => (
                      <div
                        key={fe.feature}
                        className="border border-border rounded-lg p-4 bg-secondary/20"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <p className="font-medium text-foreground mb-1">{fe.feature}</p>
                            <p className="text-sm text-muted-foreground">{fe.recommendation}</p>
                          </div>
                          <p className="text-sm font-medium text-primary whitespace-nowrap">
                            {fe.action}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Training Recommendations */}
              {profile.training_recommendations && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground">Training Recommendations</h3>
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4 space-y-3">
                    <div>
                      <p className="text-xs text-green-600 font-medium mb-1">Recommended Model</p>
                      <p className="font-medium text-foreground">
                        {profile.training_recommendations.suggested_model}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-green-600 font-medium mb-2">Preprocessing Steps</p>
                      <div className="space-y-1">
                        {profile.training_recommendations.suggested_preprocessing.map(
                          (step, idx) => (
                            <div key={idx} className="flex items-center gap-2 text-sm">
                              <ChevronRight className="w-4 h-4 text-green-600" />
                              <span className="text-foreground">{step}</span>
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Column Details Table */}
              {profile.columns && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-foreground">Column Details</h3>
                  <div className="border border-border rounded-lg overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-secondary/50 border-b border-border">
                        <tr>
                          <th className="px-4 py-3 text-left font-medium text-foreground">
                            Column
                          </th>
                          <th className="px-4 py-3 text-left font-medium text-foreground">
                            Type
                          </th>
                          <th className="px-4 py-3 text-right font-medium text-foreground">
                            Missing %
                          </th>
                          <th className="px-4 py-3 text-right font-medium text-foreground">
                            Unique
                          </th>
                          <th className="px-4 py-3 text-right font-medium text-foreground">
                            Min
                          </th>
                          <th className="px-4 py-3 text-right font-medium text-foreground">
                            Max
                          </th>
                          <th className="px-4 py-3 text-right font-medium text-foreground">
                            Mean
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(profile.columns).map(([col, info]) => (
                          <tr key={col} className="border-b border-border hover:bg-secondary/30">
                            <td className="px-4 py-3 font-medium text-foreground">{col}</td>
                            <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                              {info.dtype}
                            </td>
                            <td
                              className={`px-4 py-3 text-right ${
                                info.missing_pct > 10 ? 'text-amber-600 font-medium' : ''
                              }`}
                            >
                              {info.missing_pct?.toFixed(1)}%
                            </td>
                            <td className="px-4 py-3 text-right text-muted-foreground">
                              {info.unique_count}
                            </td>
                            <td className="px-4 py-3 text-right text-muted-foreground">
                              {info.min != null ? info.min.toFixed(2) : '—'}
                            </td>
                            <td className="px-4 py-3 text-right text-muted-foreground">
                              {info.max != null ? info.max.toFixed(2) : '—'}
                            </td>
                            <td className="px-4 py-3 text-right text-muted-foreground">
                              {info.mean != null ? info.mean.toFixed(2) : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-muted-foreground">Profile unavailable</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}