import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'

export default function HeroDetailPage() {
  const { id } = useParams()
  const heroId = Number(id)
  const { data, isLoading, error } = useQuery({ queryKey: ['hero', heroId], queryFn: () => api.hero(heroId) })

  if (isLoading) return <p className="text-deco-cream/60">Loading…</p>
  if (error || !data) return <p className="text-verdict-backfired">Hero not found.</p>

  const chartData = data.snapshots.map((s) => ({
    date: s.window_start.slice(0, 10),
    winRate: +(s.win_rate * 100).toFixed(2),
    window: s.window,
    matches: s.matches,
    patch: s.patch_id,
  }))

  return (
    <div>
      <Link to="/heroes" className="text-sm text-deco-cream/50 hover:text-deco-gold">← all heroes</Link>
      <h1 className="deco-heading text-3xl mt-2 mb-6">{data.name}</h1>

      <div className="deco-card p-5 mb-8">
        <h2 className="deco-heading text-lg mb-4">Win rate around patches</h2>
        {chartData.length === 0 ? (
          <p className="text-deco-cream/50 text-sm">No snapshots yet — run the pipeline with --snapshots.</p>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid stroke="#2a3325" strokeDasharray="3 3" />
              <XAxis dataKey="date" stroke="#8a7648" fontSize={12} />
              <YAxis domain={['auto', 'auto']} stroke="#8a7648" fontSize={12} unit="%" />
              <Tooltip
                contentStyle={{ background: '#171d15', border: '1px solid #2a3325', borderRadius: 2 }}
                labelStyle={{ color: '#c9a86a' }}
                formatter={(value: number, _name, item) => [
                  `${value}% (${item.payload.window}, ${item.payload.matches.toLocaleString()} matches)`,
                  'win rate',
                ]}
              />
              <Line type="monotone" dataKey="winRate" stroke="#c9a86a" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <h2 className="deco-heading text-lg mb-4">Change history</h2>
      <div className="space-y-3">
        {data.changes.map((c) => (
          <div key={c.id} className="deco-card p-4">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider text-deco-cream/50">{c.change_type}</span>
            </div>
            <p className="text-deco-cream/85 mt-1">{c.description}</p>
            <p className="text-xs text-deco-cream/40 mt-1 border-l-2 border-line pl-2">{c.source_line}</p>
          </div>
        ))}
        {data.changes.length === 0 && (
          <p className="text-deco-cream/50 text-sm">No recorded changes for this hero yet.</p>
        )}
      </div>
    </div>
  )
}
