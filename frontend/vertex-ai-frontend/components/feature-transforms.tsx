'use client'

import { useEffect, useState } from 'react'
import { Plus, X } from 'lucide-react'
import { datasets, FeatureTransform, FeatureOp } from '@/lib/api'

// ─── Op catalogue (mirrors shared/ml/features.py) ─────────────────────────────

type ColumnKind = 'numeric' | 'text'

const OPS: Record<FeatureOp, { label: string; description: string; kind: ColumnKind }> = {
  log:            { label: 'Log',            kind: 'numeric', description: 'log(1 + x) for skewed, non-negative columns such as income or counts' },
  bin:            { label: 'Bin',            kind: 'numeric', description: 'Split into quantile bins, so the model can learn a non-linear effect' },
  datetime_parts: { label: 'Date parts',     kind: 'text',    description: 'Year, month, day, weekday and hour from a date/time column' },
  interaction:    { label: 'Interaction',    kind: 'numeric', description: 'Multiply two columns, e.g. price × quantity' },
  target_encode:  { label: 'Target encode',  kind: 'text',    description: 'Replace each category with its average label; fitted per CV fold, so it does not leak' },
}
const DATE_PARTS = ['year', 'month', 'day', 'dayofweek', 'hour']

type Column = { name: string; numeric: boolean; min: number | null }
type ColumnProfile = { dtype: string; min?: number | null }

// ─── Small pieces ─────────────────────────────────────────────────────────────

function Chip({ active, disabled, onClick, children }: {
  active: boolean; disabled?: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className={`px-2 py-1 rounded-md border text-[11px] font-medium transition ${active
        ? 'bg-foreground text-white border-foreground'
        : 'bg-white border-border text-foreground hover:bg-secondary'} disabled:opacity-40 disabled:cursor-not-allowed`}>
      {children}
    </button>
  )
}

const toggle = (list: string[], value: string) =>
  list.includes(value) ? list.filter(v => v !== value) : [...list, value]

// ─── Editor ───────────────────────────────────────────────────────────────────

export default function FeatureTransformsEditor({ datasetId, targetColumn, value, onChange }: {
  datasetId: string
  targetColumn: string
  value: FeatureTransform[]
  onChange: (next: FeatureTransform[]) => void
}) {
  const [columns, setColumns] = useState<Column[] | null>(null)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    if (!datasetId) { setColumns(null); return }
    let stale = false
    setColumns(null); setError(null)
    datasets.profile(parseInt(datasetId))
      .then((p: unknown) => {
        if (stale) return
        const cols = (p as { columns?: Record<string, ColumnProfile> }).columns ?? {}
        setColumns(Object.entries(cols).map(([name, c]) => ({
          name,
          numeric: /int|float/.test(c.dtype),
          min: typeof c.min === 'number' ? c.min : null,
        })))
      })
      .catch(() => { if (!stale) setError('Could not read the dataset columns') })
    return () => { stale = true }
  }, [datasetId])

  // A new dataset means new columns: drop transforms that point at columns it doesn't have.
  useEffect(() => {
    if (!columns) return
    const names = new Set(columns.map(c => c.name))
    const kept = value
      .map(t => ({ ...t, columns: t.columns?.filter(c => names.has(c)),
                   pairs: t.pairs?.filter(p => p.every(c => names.has(c))) }))
      .filter(t => t.op === 'interaction' ? (t.pairs?.length ?? 0) > 0 : (t.columns?.length ?? 0) > 0)
    if (kept.length !== value.length) onChange(kept)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [columns])

  if (!datasetId) return <p className="text-xs text-muted-foreground">Select a dataset to choose columns.</p>
  if (error)      return <p className="text-xs text-red-600">{error}</p>
  if (!columns)   return <div className="h-16 bg-secondary rounded-lg animate-pulse" />

  const features = columns.filter(c => c.name !== targetColumn.trim() && c.name !== 'id')
  // Log, bin, date parts and target encode replace a column's default handling, so one column can take only one of them.
  const claimedBy = (name: string, op: FeatureOp) =>
    value.find(t => t.op !== op && t.op !== 'interaction' && t.columns?.includes(name))?.op
  const used = new Set(value.map(t => t.op))
  const update = (i: number, patch: Partial<FeatureTransform>) =>
    onChange(value.map((t, j) => (j === i ? { ...t, ...patch } : t)))

  const eligible = (op: FeatureOp) => features.filter(c =>
    OPS[op].kind === 'numeric' ? c.numeric && (op !== 'log' || c.min == null || c.min >= 0) : !c.numeric)

  return (
    <div className="space-y-3">
      {value.map((t, i) => {
        const cols = eligible(t.op)
        return (
          <div key={t.op} className="bg-white border border-border rounded-lg p-3">
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <p className="text-xs font-semibold text-foreground">{OPS[t.op].label}</p>
                <p className="text-[10px] text-muted-foreground">{OPS[t.op].description}</p>
              </div>
              <button type="button" onClick={() => onChange(value.filter((_, j) => j !== i))}
                className="text-muted-foreground hover:text-red-500" aria-label={`Remove ${OPS[t.op].label}`}>
                <X className="w-4 h-4" />
              </button>
            </div>

            {cols.length === 0 ? (
              <p className="text-[11px] text-amber-600">
                No suitable columns ({OPS[t.op].kind === 'numeric' ? 'numeric' : 'text'}
                {t.op === 'log' ? ', no negative values' : ''}) in this dataset.
              </p>
            ) : t.op === 'interaction' ? (
              <InteractionPairs columns={cols.map(c => c.name)} pairs={t.pairs ?? []}
                onChange={pairs => update(i, { pairs })} />
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {cols.map(c => {
                  const other = claimedBy(c.name, t.op)
                  return (
                    <Chip key={c.name} active={!!t.columns?.includes(c.name)} disabled={!!other}
                      onClick={() => update(i, { columns: toggle(t.columns ?? [], c.name) })}>
                      <span title={other ? `Already used by ${OPS[other].label}` : undefined}>{c.name}</span>
                    </Chip>
                  )
                })}
              </div>
            )}

            {t.op === 'bin' && (
              <label className="flex items-center gap-2 mt-2 text-[11px] text-muted-foreground">
                Bins
                <input type="number" className="input" style={{ padding: '3px 6px', fontSize: 12, width: 70 }}
                  min={2} max={100} value={t.n_bins ?? 5}
                  onChange={e => update(i, { n_bins: parseInt(e.target.value) || 5 })} />
              </label>
            )}
            {t.op === 'datetime_parts' && (
              <div className="flex flex-wrap items-center gap-1.5 mt-2">
                <span className="text-[11px] text-muted-foreground mr-1">Parts</span>
                {DATE_PARTS.map(p => (
                  <Chip key={p} active={(t.parts ?? DATE_PARTS).includes(p)}
                    onClick={() => update(i, { parts: toggle(t.parts ?? DATE_PARTS, p) })}>
                    {p}
                  </Chip>
                ))}
              </div>
            )}
          </div>
        )
      })}

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[11px] text-muted-foreground mr-1"><Plus className="w-3 h-3 inline" /> Add</span>
        {(Object.keys(OPS) as FeatureOp[]).map(op => (
          <Chip key={op} active={false} disabled={used.has(op)}
            onClick={() => onChange([...value, op === 'interaction' ? { op, pairs: [] } : { op, columns: [] }])}>
            {OPS[op].label}
          </Chip>
        ))}
      </div>
    </div>
  )
}

function InteractionPairs({ columns, pairs, onChange }: {
  columns: string[]; pairs: string[][]; onChange: (pairs: string[][]) => void
}) {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const exists = pairs.some(p => (p[0] === a && p[1] === b) || (p[0] === b && p[1] === a))
  return (
    <div className="space-y-2">
      {pairs.map((p, k) => (
        <div key={p.join('*')} className="flex items-center gap-2 text-xs">
          <span className="font-mono">{p[0]} × {p[1]}</span>
          <button type="button" onClick={() => onChange(pairs.filter((_, j) => j !== k))}
            className="text-muted-foreground hover:text-red-500" aria-label={`Remove ${p[0]} × ${p[1]}`}>
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
      <div className="flex items-center gap-2">
        <select className="input" style={{ padding: '3px 6px', fontSize: 12 }} value={a} onChange={e => setA(e.target.value)}>
          <option value="">Column…</option>
          {columns.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <span className="text-xs text-muted-foreground">×</span>
        <select className="input" style={{ padding: '3px 6px', fontSize: 12 }} value={b} onChange={e => setB(e.target.value)}>
          <option value="">Column…</option>
          {columns.filter(c => c !== a).map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button type="button" disabled={!a || !b || a === b || exists}
          onClick={() => { onChange([...pairs, [a, b]]); setA(''); setB('') }}
          className="px-2.5 py-1 rounded-md border border-border text-[11px] font-medium hover:bg-secondary disabled:opacity-40">
          Add pair
        </button>
      </div>
    </div>
  )
}

/** Drop incomplete entries before sending; the server re-validates everything. */
export function completeTransforms(transforms: FeatureTransform[]): FeatureTransform[] {
  return transforms.filter(t => t.op === 'interaction' ? (t.pairs?.length ?? 0) > 0 : (t.columns?.length ?? 0) > 0)
}
