import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'

function fmtBuyTime(seconds: number | null): string {
  if (seconds === null) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function ItemDetailPage() {
  const { id } = useParams()
  const itemId = Number(id)
  const { data, isLoading, error } = useQuery({ queryKey: ['item', itemId], queryFn: () => api.item(itemId) })

  if (isLoading) return <p className="text-deco-cream/60">Loading…</p>
  if (error || !data) return <p className="text-verdict-backfired">Item not found.</p>

  const timingChart = data.timing.map((t) => ({
    window: t.window === 'baseline' ? 'baseline' : `patch #${t.patch_id} ${t.window}`,
    early: t.win_rate_early !== null ? +(t.win_rate_early * 100).toFixed(2) : null,
    mid: t.win_rate_mid !== null ? +(t.win_rate_mid * 100).toFixed(2) : null,
    late: t.win_rate_late !== null ? +(t.win_rate_late * 100).toFixed(2) : null,
    avgBuy: t.avg_buy_time_s,
    matches: t.matches,
  }))

  return (
    <div>
      <Link to="/items" className="text-sm text-deco-cream/50 hover:text-deco-gold">← all items</Link>
      <div className="flex items-baseline gap-4 mt-2 mb-6">
        <h1 className="deco-heading text-3xl">{data.name}</h1>
        {data.tier !== null && <span className="text-sm text-deco-dim">Tier {data.tier}</span>}
        {data.cost !== null && <span className="text-sm text-deco-dim">{data.cost.toLocaleString()} souls</span>}
      </div>

      <div className="deco-card p-5 mb-8">
        <h2 className="deco-heading text-lg mb-4">Purchase timing</h2>
        {data.timing.length === 0 ? (
          <p className="text-deco-cream/50 text-sm">No timing data yet — run the pipeline with --timing.</p>
        ) : (
          <>
            <div className="grid gap-3 grid-cols-2 md:grid-cols-4 mb-6">
              {data.timing.map((t, i) => (
                <div key={i} className="deco-card p-3">
                  <p className="text-xs uppercase tracking-wider text-deco-cream/50">
                    {t.window === 'baseline' ? 'baseline' : `${t.window} patch #${t.patch_id}`}
                  </p>
                  <p className="text-xl mt-1">{fmtBuyTime(t.avg_buy_time_s)}</p>
                  <p className="text-xs text-deco-cream/40">avg buy time · {t.matches.toLocaleString()} matches</p>
                </div>
              ))}
            </div>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={timingChart}>
                <CartesianGrid stroke="#2a3325" strokeDasharray="3 3" />
                <XAxis dataKey="window" stroke="#8a7648" fontSize={11} />
                <YAxis stroke="#8a7648" fontSize={12} unit="%" domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#171d15', border: '1px solid #2a3325', borderRadius: 2 }}
                  labelStyle={{ color: '#c9a86a' }}
                  formatter={(value: number | null, name) => [value === null ? 'n/a' : `${value}%`, `${name} buy`]}
                />
                <Legend />
                <Bar dataKey="early" name="early (<12:00)" fill="#c9a86a" isAnimationActive={false} />
                <Bar dataKey="mid" name="mid (12–24:00)" fill="#8a7648" isAnimationActive={false} />
                <Bar dataKey="late" name="late (>24:00)" fill="#5a6b4a" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
            <p className="text-xs text-deco-cream/40 mt-2">
              Win rate split by when the item was bought in-match. Early &lt; 12 min, mid 12–24 min, late &gt; 24 min.
            </p>
          </>
        )}
      </div>

      <h2 className="deco-heading text-lg mb-4">Change history</h2>
      <div className="space-y-3">
        {data.changes.map((c) => (
          <div key={c.id} className="deco-card p-4">
            <span className="text-xs uppercase tracking-wider text-deco-cream/50">{c.change_type}</span>
            <p className="text-deco-cream/85 mt-1">{c.description}</p>
            <p className="text-xs text-deco-cream/40 mt-1 border-l-2 border-line pl-2">{c.source_line}</p>
          </div>
        ))}
        {data.changes.length === 0 && (
          <p className="text-deco-cream/50 text-sm">No recorded changes for this item yet.</p>
        )}
      </div>
    </div>
  )
}
