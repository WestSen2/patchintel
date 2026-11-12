import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function HeroesPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['heroes'], queryFn: api.heroes })

  if (isLoading) return <p className="text-deco-cream/60">Loading heroes…</p>
  if (error) return <p className="text-verdict-backfired">Failed to load heroes.</p>

  return (
    <div>
      <h1 className="deco-heading text-3xl mb-1">Heroes</h1>
      <p className="text-sm text-deco-cream/60 mb-8">{data?.length ?? 0} playable heroes</p>
      <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
        {data?.map((h) => (
          <Link key={h.id} to={`/heroes/${h.id}`} className="deco-card p-4 text-center hover:border-deco-dim transition-colors">
            <span className="font-display">{h.name}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
