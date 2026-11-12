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

export interface ItemDetail extends Item {
  snapshots: Snapshot[]
  changes: ChangeOut[]
}
