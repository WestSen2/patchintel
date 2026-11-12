import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { VerdictBadge } from '../components/VerdictBadge'
import type { ChangeOut, VerdictOut } from '../types'

function pct(x: number | null): string {
  return x === null ? '—' : `${(x * 100).toFixed(1)}%`
}

function ChangeTypeChip({ type }: { type: string }) {
  const colors: Record<string, string> = {
    buff: 'text-verdict-worked border-verdict-worked/40',
    nerf: 'text-verdict-backfired border-verdict-backfired/40',
    rework: 'text-verdict-shifted border-verdict-shifted/40',
    adjustment: 'text-verdict-unclear border-verdict-unclear/40',
    bugfix: 'text-verdict-noeffect border-verdict-noeffect/40',
  }
  return (
    <span className={`text-xs uppercase tracking-wider border px-2 py-0.5 rounded-sm ${colors[type] ?? 'text-gray-400 border-gray-600'}`}>
      {type}
    </span>
  )
}

function ChangeCard({ change, verdict }: { change: ChangeOut; verdict?: VerdictOut }) {
  return (
    <div className="deco-card p-5">
      <div className="flex items-center gap-2 flex-wrap">
        <ChangeTypeChip type={change.change_type} />
        <span className="text-xs text-deco-cream/50 uppercase tracking-wider">{change.entity_type}</span>
        <span className="font-display text-lg">{change.entity_name}</span>
        {verdict && <span className="ml-auto"><VerdictBadge verdict={verdict.verdict} /></span>}
      </div>
      <p className="text-deco-cream/80 mt-2">{change.description}</p>
      {change.numbers.length > 0 && (
        <ul className="text-sm text-deco-cream/60 mt-1">
          {change.numbers.map((n, i) => (
            <li key={i}>{n.stat}: {n.old} → {n.new} {n.unit}</li>
          ))}
        </ul>
      )}
      {verdict && verdict.delta_win_rate !== null && (
        <div className="mt-3 pt-3 border-t border-line text-sm grid grid-cols-2 md:grid-cols-4 gap-2">
          <div><span className="text-deco-cream/50">Win rate</span><br />{pct(verdict.pre_win_rate)} → {pct(verdict.post_win_rate)}</div>
          <div><span className="text-deco-cream/50">Delta</span><br />{(verdict.delta_win_rate * 100).toFixed(1)} pts</div>
          <div><span className="text-deco-cream/50">CI ±</span><br />{verdict.ci_half_width !== null ? `${(verdict.ci_half_width * 100).toFixed(1)} pts` : '—'}</div>
          <div><span className="text-deco-cream/50">Matches</span><br />{verdict.pre_matches.toLocaleString()} / {verdict.post_matches.toLocaleString()}</div>
        </div>
      )}
      {verdict && <p className="text-xs text-deco-cream/40 mt-2">{verdict.reason}</p>}
      <p className="text-xs text-deco-cream/40 mt-2 border-l-2 border-line pl-2">{change.source_line}</p>
    </div>
  )
}

export default function PatchDetailPage() {
  const { id } = useParams()
  const patchId = Number(id)

  const patch = useQuery({ queryKey: ['patch', patchId], queryFn: () => api.patch(patchId) })
  const impact = useQuery({ queryKey: ['impact', patchId], queryFn: () => api.patchImpact(patchId), retry: false })

  if (patch.isLoading) return <p className="text-deco-cream/60">Loading…</p>
  if (patch.error || !patch.data) return <p className="text-verdict-backfired">Patch not found.</p>

  const verdictByChangeId = new Map(
    (impact.data?.verdicts ?? []).filter((v) => v.change_id !== null).map((v) => [v.change_id as number, v]),
  )

  return (
    <div>
      <Link to="/" className="text-sm text-deco-cream/50 hover:text-deco-gold">← all patches</Link>
      <h1 className="deco-heading text-3xl mt-2">{patch.data.title}</h1>
      <p className="text-sm text-deco-cream/60 mb-2">
        {patch.data.patch_date ? patch.data.patch_date.slice(0, 10) : 'date unknown'} ·{' '}
        <a className="underline hover:text-deco-gold" href={patch.data.source_url} target="_blank" rel="noreferrer">source</a>
        {!patch.data.llm_generated && ' · heuristic summary (no LLM configured)'}
      </p>
      {patch.data.summary && <div className="deco-card p-5 my-6 text-deco-cream/85">{patch.data.summary}</div>}

      <h2 className="deco-heading text-xl mb-4">
        Changes {impact.data && impact.data.verdicts.length > 0 && <span className="text-sm text-deco-cream/50">— with measured verdicts</span>}
      </h2>
      <div className="space-y-4">
        {patch.data.changes.map((c) => (
          <ChangeCard key={c.id} change={c} verdict={verdictByChangeId.get(c.id)} />
        ))}
        {patch.data.changes.length === 0 && (
          <p className="text-deco-cream/50">No structured changes extracted for this patch yet.</p>
        )}
      </div>
    </div>
  )
}
