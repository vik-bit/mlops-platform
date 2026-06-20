'use client'

import { useState, useRef } from 'react'
import { Upload, Trash2, FileText, BarChart3, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { useDatasets } from '@/lib/hooks'
import { datasets as datasetsApi, Dataset, DatasetProfile } from '@/lib/api'
import ProfileModal from '@/components/profile_modal'

export default function DatasetsView() {
  const { data, loading, refresh } = useDatasets()
  const datasetList: Dataset[] = data ?? []

  const [uploading, setUploading]             = useState(false)
  const [selectedFiles, setSelectedFiles]     = useState<File[]>([])
  const [error, setError]                     = useState<string | null>(null)
  const [deleting, setDeleting]               = useState<number | null>(null)

  // Which dataset's modal is open (null = closed). Renamed from the old
  // `profileId` toggle to reflect the new "Analyze" button — same role,
  // always opens rather than toggling closed on a second click.
  const [analyzingId, setAnalyzingId]         = useState<number | null>(null)
  const [profile, setProfile]                 = useState<DatasetProfile | null>(null)
  const [selectedTargets, setSelectedTargets] = useState<Record<number, string>>({})
  const [profileLoading, setProfileLoading]   = useState(false)
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
    try {
      await datasetsApi.delete(id)
      if (analyzingId === id) { setAnalyzingId(null); setProfile(null) }
      refresh()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    } finally { setDeleting(null) }
  }

  // Opens the modal and fetches the profile when "Analyze" is clicked.
  const openProfile = async (id: number) => {
    setAnalyzingId(id)
    setProfileLoading(true)
    setProfile(null)
    try {
      const p = await datasetsApi.profile(id, selectedTargets[id] || '')
      setProfile(p)
    } catch {
      setProfile(null)
    } finally {
      setProfileLoading(false)
    }
  }

  const closeProfile = () => {
    setAnalyzingId(null)
    setProfile(null)
  }

  const reloadProfile = async (datasetId: number, target: string) => {
    setSelectedTargets(prev => ({ ...prev, [datasetId]: target }))
    setProfileLoading(true)
    try {
      const p = await datasetsApi.profile(datasetId, target)
      setProfile(p)
    } catch (err) {
      console.error(err)
    } finally {
      setProfileLoading(false)
    }
  }

  const activeDataset = datasetList.find(d => d.id === analyzingId)

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
        <div className="mb-8 border-2 border-dashed border-border rounded-xl p-8 hover:border-foreground/30 transition-colors">
          <div className="text-center">
            <div className="w-12 h-12 rounded-xl bg-secondary flex items-center justify-center mx-auto mb-3">
              <FileText className="w-6 h-6 text-muted-foreground" />
            </div>
            <h3 className="text-base font-semibold text-foreground mb-1">Upload New Dataset</h3>
            <p className="text-sm text-muted-foreground mb-4">CSV files supported</p>
            <input ref={fileInputRef} type="file" multiple onChange={handleFileSelect} className="hidden" accept=".csv" id="dataset-file-input" />
            <label
              htmlFor="dataset-file-input"
              className="inline-flex items-center px-5 py-2.5 rounded-lg bg-foreground text-white text-sm font-medium hover:bg-foreground/90 transition cursor-pointer"
            >
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

        {/* Dataset table */}
        <div className="bg-white border border-border rounded-xl overflow-hidden mb-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]">Filename</TableHead>
                <TableHead>Path</TableHead>
                <TableHead>Uploaded</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-10 text-muted-foreground text-sm">
                    Loading…
                  </TableCell>
                </TableRow>
              ) : datasetList.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-10 text-muted-foreground text-sm">
                    No datasets uploaded yet
                  </TableCell>
                </TableRow>
              ) : (
                datasetList.map(ds => (
                  <TableRow key={ds.id}>
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-secondary shrink-0">
                          <FileText className="w-4 h-4 text-muted-foreground" />
                        </div>
                        <span className="font-medium text-foreground text-sm">{ds.filename}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs text-muted-foreground bg-secondary/60 rounded px-2 py-1 inline-block max-w-[260px] truncate">
                        {ds.path}
                      </code>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(ds.created_at).toLocaleDateString(undefined, {
                        year: 'numeric', month: 'short', day: 'numeric',
                      })}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                       <Button
  variant="outline"
  size="sm"
  onClick={() => openProfile(ds.id)}
  disabled={analyzingId === ds.id && profileLoading}
  className="h-8 gap-1.5 bg-blue-500 text-white hover:bg-blue-600 disabled:bg-blue-400 disabled:cursor-not-allowed"
>
                          {analyzingId === ds.id && profileLoading ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <BarChart3 className="w-3.5 h-3.5" />
                          )}
                          Analyze
                        </Button>
                        <button
                          onClick={() => handleDelete(ds.id)}
                          disabled={deleting === ds.id}
                          className="p-2 rounded-lg hover:bg-red-50 text-muted-foreground hover:text-red-500 transition disabled:opacity-50"
                          title="Delete dataset"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
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

      {/* Profile modal — replaces the old inline expandable table row.
          Every section from the original (overview, warnings, target analysis,
          feature importance, outliers, distributions, correlations, feature
          engineering, training recommendations, column table) lives inside
          ProfileModal already, so nothing is lost — just relocated. */}
      <ProfileModal
        open={analyzingId !== null}
        onClose={closeProfile}
        profile={profile}
        datasetName={activeDataset?.filename ?? ''}
        selectedTarget={analyzingId != null ? (selectedTargets[analyzingId] ?? '') : ''}
        onTargetChange={(target) => {
          if (analyzingId != null) {
            setSelectedTargets(prev => ({ ...prev, [analyzingId]: target }))
          }
        }}
        onReloadProfile={() => {
          if (analyzingId != null) {
            reloadProfile(analyzingId, selectedTargets[analyzingId] ?? '')
          }
        }}
        loading={profileLoading}
      />
    </div>
  )
}