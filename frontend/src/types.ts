// Mirrors backend/app/schemas.py — keep in sync.

export interface PatchListItem {
  id: number
  title: string
  patch_date: string | null
  status: string
  summary: string
  change_count: number
}

export interface ChangeOut {
  id: number
  entity_type: string
  entity_name: string
  entity_id: number | null
  change_type: string
  description: string
  numbers: { stat: string; old: string; new: string; unit: string }[]
  source_line: string
}

export interface PatchDetail {
  id: number
  title: string
  patch_date: string | null
  source_url: string
  status: string
  summary: string
  llm_generated: boolean
  changes: ChangeOut[]
}

export interface VerdictOut {
  id: number
  patch_id: number
  change_id: number | null
  entity_type: string
  entity_id: number
  expected_direction: string
  pre_win_rate: number | null
  post_win_rate: number | null
  delta_win_rate: number | null
  pre_pick_rate: number | null
  post_pick_rate: number | null
  pre_matches: number
  post_matches: number
  ci_half_width: number | null
  verdict: string
  reason: string
}

export interface PatchImpact {
  patch_id: number
  title: string
  patch_date: string | null
  verdicts: VerdictOut[]
}

export interface Hero {
  id: number
  name: string
}

export interface Snapshot {
  patch_id: number | null
  window: string
  window_start: string
  window_end: string
  truncated: boolean
  win_rate: number
  pick_rate: number | null
  matches: number
}

export interface HeroDetail {
  id: number
  name: string
  snapshots: Snapshot[]
  changes: ChangeOut[]
}

export interface Item {
  id: number
  name: string
  tier: number | null
  cost: number | null
}

export interface TimingOut {
  patch_id: number | null
  window: string
  avg_buy_time_s: number | null
  avg_buy_time_relative: number | null
  win_rate_early: number | null
  win_rate_mid: number | null
  win_rate_late: number | null
  matches: number
}

export interface ItemDetail extends Item {
  snapshots: Snapshot[]
  changes: ChangeOut[]
  timing: TimingOut[]
}

// ------------------------------------------------------------------ M3 types

export interface Me {
  id: number
  steam_id: string
  display_name: string
  avatar_url: string
  timezone: string
  last_sync_at: string | null
}

export interface AnalyticsBucket {
  label: string
  win_rate: number | null
  avg_kda: number | null
  matches: number
}

export interface MyAnalytics {
  matches: number
  win_rate: number | null
  avg_kda: number | null
  by_session_game_index: AnalyticsBucket[]
  after_loss_streak: AnalyticsBucket[]
  by_hour: AnalyticsBucket[]
  by_weekday: AnalyticsBucket[]
  top_heroes: { hero_id: number; hero_name: string | null; matches: number; win_rate: number; avg_kda: number }[]
}

export interface MyPatchImpact {
  hero_ids: number[]
  patches: {
    patch_id: number
    title: string
    patch_date: string | null
    verdicts: VerdictOut[]
  }[]
}

export interface SyncResult {
  imported: number
  sessions: number
}

export interface MyMatch {
  id: number
  match_id: number
  played_at: string
  duration_s: number
  hero_id: number | null
  result: string
  kills: number
  deaths: number
  assists: number
  net_worth: number | null
  session_id: number | null
}

export interface PurchaseCurvePoint {
  bucket_start_s: number
  wins: number
  losses: number
  matches: number
  win_rate: number | null
}
