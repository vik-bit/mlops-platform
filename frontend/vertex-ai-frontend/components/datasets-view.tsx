'use client'

import { useState, useRef } from 'react'
import { Upload, Trash2, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDatasets } from '@/lib/hooks'
import { datasets as datasetsApi, Dataset, DatasetProfile } from '@/lib/api'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const getTopCorrelations = (
  matrix: Record<string, Record<string, number>>
) => {
  const pairs: {
    featureA: string
    featureB: string
    correlation: number
  }[] = []

  Object.entries(matrix).forEach(([featureA, values]) => {
    Object.entries(values).forEach(([featureB, corr]) => {
      if (
        featureA !== featureB &&
        featureA < featureB
      ) {
        pairs.push({
          featureA,
          featureB,
          correlation: Math.abs(corr),
        })
      }
    })
  })

  return pairs
    .sort(
      (a, b) =>
        b.correlation - a.correlation
    )
    .slice(0, 10)
}

export default function DatasetsView() {
  const { data, loading, refresh } = useDatasets()
  const datasetList: Dataset[] = data ?? []

  const [uploading, setUploading]           = useState(false)
  const [selectedFiles, setSelectedFiles]   = useState<File[]>([])
  const [error, setError]                   = useState<string | null>(null)
  const [deleting, setDeleting]             = useState<number | null>(null)
  const [profileId, setProfileId]           = useState<number | null>(null)
  const [profile, setProfile]               = useState<DatasetProfile | null>(null)
  const [selectedTargets, setSelectedTargets] = useState<
  Record<number, string>
>({})
  const [profileLoading, setProfileLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setSelectedFiles(Array.from(e.target.files))
  }

  const handleUpload = async () => {
    setUploading(true); setError(null)
    try {
      for (const file of selectedFiles) await datasetsApi.upload(file)
      setSelectedFiles([])
      if (fileInputRef.current) fileInputRef.current.value = ''
      refresh()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally { setUploading(false) }
  }

  const handleDelete = async (id: number) => {
    setDeleting(id)
    try { await datasetsApi.delete(id); if (profileId === id) setProfileId(null); refresh() }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Delete failed') }
    finally { setDeleting(null) }
  }

  const toggleProfile = async (id: number) => {
    if (profileId === id) { setProfileId(null); setProfile(null); return }
    setProfileId(id); setProfileLoading(true); setProfile(null)
    try {
      const p = await datasetsApi.profile(
  id,
  selectedTargets[id] || ''
)
      setProfile(p)
    } catch { setProfile(null) }
    finally { setProfileLoading(false) }
  }
  const reloadProfile = async (
  datasetId: number,
  target: string
) => {
  setSelectedTargets(prev => ({
    ...prev,
    [datasetId]: target,
  }))

  setProfileLoading(true)

  try {
    const p = await datasetsApi.profile(
      datasetId,
      target
    )

    setProfile(p)
  } catch (err) {
    console.error(err)
  } finally {
    setProfileLoading(false)
  }
}

  return (
    <div className="flex-1 overflow-auto bg-white">
      {/* Header */}
      <div className="border-b border-border bg-white sticky top-0 z-10">
        <div className="px-8 py-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Datasets</h1>
            <p className="text-muted-foreground mt-1">Upload and manage your training data</p>
          </div>
          <Button onClick={() => fileInputRef.current?.click()}>
            <Upload className="w-4 h-4 mr-2" />Upload Dataset
          </Button>
          
        </div>
      </div>

      <div className="p-8">
        {/* Upload zone */}
        <div className="mb-8 border-2 border-dashed border-border rounded-xl p-8 hover:border-foreground/20 transition">
          <div className="text-center">
            <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <h3 className="text-base font-semibold text-foreground mb-1">Upload New Dataset</h3>
            <p className="text-sm text-muted-foreground mb-4">CSV files supported</p>
            <input ref={fileInputRef} type="file" multiple onChange={handleFileSelect} className="hidden" accept=".csv" />
            <label htmlFor="file-input" onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center px-5 py-2.5 rounded-lg bg-foreground text-white text-sm font-medium hover:bg-foreground/90 transition cursor-pointer">
              <Upload className="w-4 h-4 mr-2" />Select Files
            </label>
            {selectedFiles.length > 0 && (
              <>
                <p className="mt-3 text-sm text-foreground">{selectedFiles.length} file(s): {selectedFiles.map(f => f.name).join(', ')}</p>
                <Button onClick={handleUpload} disabled={uploading} className="mt-3">
                  {uploading ? 'Uploading…' : 'Upload Files'}
                </Button>
              </>
            )}
            {error && <p className="mt-3 text-sm text-red-500">{error}</p>}
          </div>
        </div>

        {/* Table */}
        <div className="bg-white border border-border rounded-xl overflow-hidden mb-6">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ padding: '12px 20px' }}>Filename</th>
                <th style={{ padding: '12px 20px' }}>Path</th>
                <th style={{ padding: '12px 20px' }}>Uploaded</th>
                <th style={{ padding: '12px 20px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="text-center py-10 text-muted-foreground text-sm">Loading…</td></tr>
              ) : datasetList.length === 0 ? (
                <tr><td colSpan={4} className="text-center py-10 text-muted-foreground text-sm">No datasets uploaded yet</td></tr>
              ) : datasetList.map(ds => (
                <>
                  <tr key={ds.id}>
                    <td style={{ padding: '10px 20px' }}>
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                        <span className="font-medium text-foreground text-sm">{ds.filename}</span>
                      </div>
                    </td>
                    <td style={{ padding: '10px 20px', fontFamily: 'monospace', fontSize: 11, color: '#b8b8b4', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ds.path}
                    </td>
                    <td style={{ padding: '10px 20px', fontSize: 12, color: '#888' }}>
                      {new Date(ds.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '10px 20px', textAlign: 'right' }}>
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => toggleProfile(ds.id)}
                          className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition"
                          title="View profile">
                          {profileId === ds.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>
                        <button onClick={() => handleDelete(ds.id)} disabled={deleting === ds.id}
                          className="p-1.5 rounded-lg hover:bg-red-50 text-muted-foreground hover:text-red-500 transition">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>

                  {/* Profile panel */}
                  {profileId === ds.id && (
                    <tr key={`profile-${ds.id}`}>
                      <td colSpan={4} style={{ padding: 0, background: '#fafaf8', borderTop: '1px solid #f0f0ee' }}>
                        <div className="p-5">
                          {profileLoading ? (
                            <p className="text-sm text-muted-foreground">Loading profile…</p>
                          ) : profile ? (
                            <div>
                              <div className="flex items-center gap-6 mb-4 text-sm">
                                <div className="mb-6 flex items-center gap-3">
  <div>
    <label className="block text-xs text-muted-foreground mb-1">
      Target Column
    </label>

    <select
      className="border rounded-md px-3 py-2 text-sm min-w-[220px]"
      value={
        selectedTargets[ds.id] || ''
      }
      onChange={(e) =>
        setSelectedTargets(prev => ({
          ...prev,
          [ds.id]: e.target.value,
        }))
      }
    >
      <option value="">
        No target selected
      </option>

      {Object.keys(profile.columns).map(
        col => (
          <option
            key={col}
            value={col}
          >
            {col}
          </option>
        )
      )}
    </select>
  </div>

  <Button
    className="mt-5"
    disabled={
      !selectedTargets[ds.id]
    }
    onClick={() =>
      reloadProfile(
        ds.id,
        selectedTargets[ds.id]
      )
    }
  >
    Reload Analysis
  </Button>
</div>
                                <span className="text-muted-foreground">Rows: <b className="text-foreground">{profile.row_count?.toLocaleString()}</b></span>
                                <span className="text-muted-foreground">Columns: <b className="text-foreground">{profile.column_count}</b></span>
                                {profile.imbalance_warning && (
                                  <span className="text-amber-600 text-xs bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">⚠ {profile.imbalance_warning}</span>
                                )}
                              </div>
                              <div className="overflow-x-auto">
                                <div className="grid grid-cols-4 gap-4 mb-6">
  <div className="bg-white border rounded-lg p-3">
    <div className="text-xs text-muted-foreground">
      Rows
    </div>
    <div className="font-bold">
      {profile.row_count.toLocaleString()}
    </div>
  </div>

  <div className="bg-white border rounded-lg p-3">
    <div className="text-xs text-muted-foreground">
      Columns
    </div>
    <div className="font-bold">
      {profile.column_count}
    </div>
  </div>

  <div className="bg-white border rounded-lg p-3">
    <div className="text-xs text-muted-foreground">
      Missing %
    </div>
    <div className="font-bold">
      {profile.missing_pct ?? 0}%
    </div>
  </div>

  <div className="bg-white border rounded-lg p-3">
    <div className="text-xs text-muted-foreground">
      Duplicate Rows
    </div>
    <div className="font-bold">
      0
    </div>
  </div>
</div>
{profile.warnings?.length ? (
  <div className="mb-6">
    <h3 className="font-semibold mb-2">
      Dataset Warnings
    </h3>

    <div className="space-y-2">
      {profile.warnings.map((warning, index) => (
        <div
          key={index}
          className="bg-amber-50 border border-amber-200 text-amber-700 rounded p-2 text-sm"
        >
          ⚠ {warning}
        </div>
      ))}
    </div>
  </div>
) : null}
{profile.target && (
  <div className="mb-6">
    <h3 className="font-semibold mb-3">
      Target Analysis
    </h3>

    <div className="grid grid-cols-4 gap-4">
      <div>
        <div className="text-xs text-muted-foreground">
          Target
        </div>
        <div className="font-medium">
          {profile.target.column}
        </div>
      </div>

      <div>
        <div className="text-xs text-muted-foreground">
          Type
        </div>
        <div className="font-medium">
          {profile.target.dtype}
        </div>
      </div>

      <div>
        <div className="text-xs text-muted-foreground">
          Suggested Task
        </div>
        <div className="font-medium">
          {profile.target.suggested_task}
        </div>
      </div>

      <div>
        <div className="text-xs text-muted-foreground">
          Classes
        </div>
        <div className="font-medium">
          {profile.target.n_unique}
        </div>
      </div>
    </div>
  </div>
)}

{(profile.feature_engineering?.length ?? 0) > 0 && (
  <table>
    <thead>
      <tr>
        <th>Feature</th>
        <th>Issue</th>
        <th>Suggested Fix</th>
      </tr>
    </thead>

    <tbody>
      {profile.feature_engineering?.map(fe => (
        <tr key={fe.feature}>
          <td>{fe.feature}</td>
          <td>{fe.recommendation}</td>
          <td>{fe.action}</td>
        </tr>
      ))}
    </tbody>
  </table>
)}
{profile.training_recommendations && (
  <div>
    <div>
      Recommended Model:
      {profile.training_recommendations.suggested_model}
    </div>

    <div>
      Preprocessing:
      {profile.training_recommendations.suggested_preprocessing.join(', ')}
    </div>
  </div>
)}
{profile.feature_rankings?.length ? (
  <div className="mb-6">
    <h3 className="font-semibold mb-3">
      Feature Importance
    </h3>

    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={profile.feature_rankings}
      >
        <XAxis dataKey="feature" />
        <YAxis />
        <Tooltip />
        <Bar dataKey="score" />
      </BarChart>
    </ResponsiveContainer>
  </div>
) : null}
{profile.outliers ? (
  <div className="mb-6">
    <h3 className="font-semibold mb-3">
      Outliers
    </h3>

    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={Object.entries(profile.outliers).map(
          ([feature, count]) => ({
            feature,
            count,
          })
        )}
      >
        <XAxis dataKey="feature" />
        <YAxis />
        <Tooltip />
        <Bar dataKey="count" />
      </BarChart>
    </ResponsiveContainer>
  </div>
) : null}
{profile.distributions &&
  
  Object.entries(profile.distributions).map(
    ([column, dist]) => (
      <div
        key={column}
        className="mb-8"
      >
        <h4 className="font-medium mb-2">
          {column}
        </h4>

        <ResponsiveContainer
          width="100%"
          height={250}
        >
          <BarChart
            data={dist.bins.map(
              (bin, index) => ({
                bin,
                count:
                  dist.counts[index],
              })
            )}
          >
            <XAxis dataKey="bin" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    )
  )}

  {profile.correlation_matrix && (
  <div className="mb-6">
    <h3 className="font-semibold mb-3">
      Strongest Correlations
    </h3>

    <ResponsiveContainer
      width="100%"
      height={350}
    >
      <BarChart
        layout="vertical"
        data={getTopCorrelations(
          profile.correlation_matrix
        ).map(item => ({
          feature:
            `${item.featureA} ↔ ${item.featureB}`,
          correlation:
            Number(
              item.correlation.toFixed(3)
            ),
        }))}
      >
        <XAxis type="number" />
        <YAxis
          type="category"
          dataKey="feature"
          width={220}
        />
        <Tooltip />
        <Bar dataKey="correlation" />
      </BarChart>
    </ResponsiveContainer>
  </div>
)}

                                <table className="data-table text-xs">
                                  <thead>
                                    <tr>
                                      <th>Column</th><th>Type</th><th>Missing %</th><th>Unique</th><th>Min</th><th>Max</th><th>Mean</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {Object.entries(profile.columns ?? {}).map(([col, info]) => (
                                      <tr key={col}>
                                        <td style={{ fontWeight: 500, color: '#111' }}>{col}</td>
                                        <td style={{ fontFamily: 'monospace' }}>{info.dtype}</td>
                                        <td style={{ color: info.missing_pct > 10 ? '#d97706' : undefined }}>{info.missing_pct?.toFixed(1)}%</td>
                                        <td>{info.unique_count}</td>
                                        <td>{info.min != null ? info.min.toFixed(2) : '—'}</td>
                                        <td>{info.max != null ? info.max.toFixed(2) : '—'}</td>
                                        <td>{info.mean != null ? info.mean.toFixed(2) : '—'}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          ) : (
                            <p className="text-sm text-muted-foreground">Profile unavailable</p>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white border border-border rounded-xl p-5">
            <p className="text-sm text-muted-foreground mb-1">Total Datasets</p>
            <p className="text-3xl font-bold text-foreground">{datasetList.length}</p>
          </div>
          <div className="bg-white border border-border rounded-xl p-5">
            <p className="text-sm text-muted-foreground mb-1">Available for Training</p>
            <p className="text-3xl font-bold text-foreground">{datasetList.length}</p>
          </div>
        </div>
      </div>
    </div>
  )
}