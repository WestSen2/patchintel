import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function PatchesPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['patches'], queryFn: api.patches })

  if (isLoading) return <p className="text-deco-cream/60">Loading patches…</p>
  if (error) return <p className="text-verdict-backfired">Failed to load patches — is the backend running on :8000?</p>

  return (
    <div>
      <h1 className="deco-heading text-3xl mb-1">Patch History</h1>
      <p className="text-sm text-deco-cream/60 mb-8">
        Every Deadlock patch, parsed into structured changes — with measured verdicts on what each change did.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        {data?.map((p) => (
          <Link key={p.id} to={`/patches/${p.id}`} className="deco-card p-5 block hover:border-deco-dim transition-colors">
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-display text-lg text-deco-cream">{p.title}</h2>
              <span className="text-xs text-deco-cream/50 whitespace-nowrap">
                {p.patch_date ? p.patch_date.slice(0, 10) : 'date unknown'}
              </span>
            </div>
            <p className="text-sm text-deco-cream/70 mt-2 line-clamp-2">{p.summary}</p>
            <p className="text-xs text-deco-dim mt-3">{p.change_count} changes</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
