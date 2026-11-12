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
  const curve = useQuery({
    queryKey: ['purchase-curve', itemId],
    queryFn: () => api.purchaseCurve(itemId),
    enabled: !!data,
  })

  if (isLoading) return <p className="text-deco-cream/60">Loading…</p>
  if (error || !data) return <p className="text-verdict-backfired">Item not found.</p>

  const curveData = (curve.data ?? []).map((p) => ({
    minute: p.bucket_start_s / 60,
    winRate: p.win_rate !== null ? +(p.win_rate * 100).toFixed(2) : null,
    matches: p.matches,
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
        {data.timing.length > 0 && (
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
        )}
        {curve.isLoading ? (
          <p className="text-deco-cream/50 text-sm">Building purchase-time curve…</p>
        ) : curveData.length === 0 ? (
          <p className="text-deco-cream/50 text-sm">No curve data available.</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={curveData}>
                <CartesianGrid stroke="#2a3325" strokeDasharray="3 3" />
                <XAxis
                  dataKey="minute"
                  stroke="#8a7648"
                  fontSize={12}
                  unit="m"
                  type="number"
                  domain={[0, 50]}
                  tickCount={11}
                />
                <YAxis stroke="#8a7648" fontSize={12} unit="%" domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ background: '#171d15', border: '1px solid #2a3325', borderRadius: 2 }}
                  labelStyle={{ color: '#c9a86a' }}
                  labelFormatter={(minute) => `bought at ~${minute}:00`}
                  formatter={(value: number | null, _name, item) => [
                    value === null
                      ? 'no data'
                      : `${value}% (${item.payload.matches.toLocaleString()} matches${item.payload.matches < 100 ? ', low sample' : ''})`,
                    'win rate',
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="winRate"
                  stroke="#c9a86a"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
            <p className="text-xs text-deco-cream/40 mt-2">
              Win rate by exact purchase time (2-minute slices, last ~30 days).
              Hover any point for its sample size — treat low-sample points as noise.
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
