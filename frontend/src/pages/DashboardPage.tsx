import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { meApi } from '../api'
import type { AnalyticsBucket } from '../types'
import { VerdictBadge } from '../components/VerdictBadge'

const LOW_SAMPLE = 20

function pct(v: number | null): string {
  return v === null ? 'n/a' : `${(v * 100).toFixed(1)}%`
}

function BucketChart({ title, buckets, dataKey, hint }: {
  title: string
  buckets: AnalyticsBucket[]
  hint: string
}) {
  const data = buckets.map((b) => ({
    label: b.label,
    winRate: b.win_rate !== null ? +(b.win_rate * 100).toFixed(1) : null,
    matches: b.matches,
    low: b.matches < LOW_SAMPLE,
  }))
  return (
    <div className="deco-card p-5">
      <h3 className="deco-heading text-lg mb-1">{title}</h3>
      <p className="text-xs text-deco-cream/50 mb-4">{hint}</p>
      {data.length === 0 ? (
        <p className="text-deco-cream/50 text-sm">No data yet — sync your matches.</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data}>
            <CartesianGrid stroke="#2a3325" strokeDasharray="3 3" />
            <XAxis dataKey="label" stroke="#8a7648" fontSize={11} />
            <YAxis stroke="#8a7648" fontSize={12} unit="%" domain={[0, 100]} />
            <Tooltip
              contentStyle={{ background: '#171d15', border: '1px solid #2a3325', borderRadius: 2 }}
              labelStyle={{ color: '#c9a86a' }}
              formatter={(value: number | null, _name, item) => [
                value === null ? 'n/a' : `${value}% (${item.payload.matches} matches${item.payload.low ? ', low sample' : ''})`,
                dataKey,
              ]}
            />
            <Bar dataKey="winRate" name="win rate" fill="#c9a86a" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

export default function DashboardPage() {
  const queryClient = useQueryClient()
  const me = useQuery({ queryKey: ['me'], queryFn: meApi.me, retry: false })
  const analytics = useQuery({
    queryKey: ['me-analytics'],
    queryFn: meApi.analytics,
    enabled: !!me.data,
  })
  const impact = useQuery({
    queryKey: ['me-impact'],
    queryFn: meApi.patchImpact,
    enabled: !!me.data,
  })
  const sync = useMutation({
    mutationFn: meApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
      queryClient.invalidateQueries({ queryKey: ['me-analytics'] })
      queryClient.invalidateQueries({ queryKey: ['me-impact'] })
    },
  })

  if (me.isLoading) return <p className="text-deco-cream/60">Loading…</p>

  if (!me.data) {
    return (
      <div className="deco-card p-8 max-w-md mx-auto text-center mt-12">
        <h1 className="deco-heading text-2xl mb-3">Personal analytics</h1>
        <p className="text-deco-cream/70 text-sm mb-6">
          Sign in with Steam to sync your match history and see session decay,
          tilt metrics, and what each patch did to your hero pool.
        </p>
        <a
          href="/api/auth/steam/login"
          className="inline-block px-6 py-2 border border-deco-gold text-deco-gold hover:bg-deco-gold hover:text-deco-ink transition-colors"
        >
          Sign in through Steam
        </a>
      </div>
    )
  }

  const a = analytics.data
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          {me.data.avatar_url && (
            <img src={me.data.avatar_url} alt="" className="w-10 h-10 border border-line" />
          )}
          <div>
            <h1 className="deco-heading text-3xl">{me.data.display_name}</h1>
            <p className="text-xs text-deco-cream/50">
              {me.data.last_sync_at
                ? `last synced ${me.data.last_sync_at.slice(0, 16).replace('T', ' ')} UTC`
                : 'never synced'}
            </p>
          </div>
        </div>
        <button
          onClick={() => sync.mutate()}
          disabled={sync.isPending}
          className="px-4 py-2 border border-deco-gold text-deco-gold hover:bg-deco-gold hover:text-deco-ink transition-colors text-sm disabled:opacity-40"
        >
          {sync.isPending ? 'Syncing…' : 'Sync matches'}
        </button>
      </div>
      {sync.isError && (
        <p className="text-verdict-backfired text-sm mb-4">
          Sync failed — {String(sync.error)}
        </p>
      )}
      {sync.data && (
        <p className="text-deco-cream/70 text-sm mb-4">
          Imported {sync.data.imported} new matches across {sync.data.sessions} sessions.
        </p>
      )}

      {a && (
        <p className="text-deco-cream/70 text-sm mb-6">
          {a.matches} matches · {pct(a.win_rate)} win rate · {a.avg_kda ?? 'n/a'} avg KDA
          {a.matches < LOW_SAMPLE && (
            <span className="text-deco-dim"> — low sample, treat every number below as noise</span>
          )}
        </p>
      )}

      <div className="grid gap-6 md:grid-cols-2 mb-8">
        {a && (
          <>
            <BucketChart
              title="Session decay"
              buckets={a.by_session_game_index}
              dataKey="win rate"
              hint="Win rate by game number within a session. If game 5+ drops hard, stop queueing."
            />
            <BucketChart
              title="Tilt check"
              buckets={a.after_loss_streak}
              dataKey="win rate"
              hint="Your win rate in games played right after a loss streak of that length."
            />
            <BucketChart
              title="Time of day"
              buckets={a.by_hour}
              dataKey="win rate"
              hint="Win rate by local hour the match started."
            />
            <BucketChart
              title="Day of week"
              buckets={a.by_weekday}
              dataKey="win rate"
              hint="Win rate by weekday."
            />
          </>
        )}
      </div>

      <h2 className="deco-heading text-lg mb-3">Your hero pool</h2>
      <div className="deco-card p-4 mb-8">
        {a && a.top_heroes.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-deco-cream/50 text-xs uppercase tracking-wider">
                <th className="pb-2">Hero</th>
                <th className="pb-2">Matches</th>
                <th className="pb-2">Win rate</th>
                <th className="pb-2">Avg KDA</th>
              </tr>
            </thead>
            <tbody>
              {a.top_heroes.map((h) => (
                <tr key={h.hero_id} className="border-t border-line">
                  <td className="py-2">
                    <Link to={`/heroes/${h.hero_id}`} className="text-deco-gold hover:underline">
                      {h.hero_name ?? `hero #${h.hero_id}`}
                    </Link>
                  </td>
                  <td>{h.matches}</td>
                  <td>{pct(h.win_rate)}</td>
                  <td>{h.avg_kda}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-deco-cream/50 text-sm">Sync your matches to see your hero pool.</p>
        )}
      </div>

      <h2 className="deco-heading text-lg mb-3">Patches affecting your pool</h2>
      <div className="space-y-3">
        {impact.data?.patches.map((p) => (
          <Link key={p.patch_id} to={`/patches/${p.patch_id}`} className="deco-card p-4 block hover:border-deco-gold transition-colors">
            <p className="text-deco-cream/85">{p.title}</p>
            <div className="flex flex-wrap gap-2 mt-2">
              {p.verdicts.map((v) => (
                <VerdictBadge key={v.id} verdict={v.verdict} />
              ))}
            </div>
          </Link>
        ))}
        {impact.data && impact.data.patches.length === 0 && (
          <p className="text-deco-cream/50 text-sm">No patch verdicts touch your heroes yet.</p>
        )}
      </div>
    </div>
  )
}
