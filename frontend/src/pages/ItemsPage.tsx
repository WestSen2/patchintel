import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

export default function ItemsPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['items'], queryFn: api.items })

  if (isLoading) return <p className="text-deco-cream/60">Loading items…</p>
  if (error) return <p className="text-verdict-backfired">Failed to load items.</p>

  const byTier = new Map<number, typeof data>()
  for (const item of data ?? []) {
    const tier = item.tier ?? 0
    byTier.set(tier, [...(byTier.get(tier) ?? []), item])
  }

  return (
    <div>
      <h1 className="deco-heading text-3xl mb-1">Items</h1>
      <p className="text-sm text-deco-cream/60 mb-8">
        {data?.length ?? 0} standard shop items (Street Brawl legendaries excluded)
      </p>
      {[...byTier.entries()].sort(([a], [b]) => a - b).map(([tier, items]) => (
        <div key={tier} className="mb-8">
          <h2 className="deco-heading text-lg mb-3">{tier > 0 ? `Tier ${tier}` : 'Other'}</h2>
          <div className="grid gap-2 grid-cols-2 md:grid-cols-4">
            {items?.map((i) => (
              <div key={i.id} className="deco-card p-3 flex justify-between items-center">
                <span>{i.name}</span>
                {i.cost !== null && <span className="text-xs text-deco-dim">{i.cost.toLocaleString()}</span>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
