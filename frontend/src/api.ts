import type {
  Hero,
  HeroDetail,
  Item,
  ItemDetail,
  Me,
  MyAnalytics,
  MyMatch,
  MyPatchImpact,
  PatchDetail,
  PatchImpact,
  PatchListItem,
  SyncResult,
} from './types'

// In dev, empty base -> Vite proxies /api to localhost:8000.
// In production, set VITE_API_BASE to the deployed backend URL.
export const BASE: string = import.meta.env.VITE_API_BASE ?? ''

export interface Health {
  status: string
  version: string
  demo_mode: boolean
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { credentials: 'include' })
  if (!resp.ok) throw new Error(`${path} -> ${resp.status}`)
  return resp.json() as Promise<T>
}

export const api = {
  patches: () => get<PatchListItem[]>('/api/patches'),
  patch: (id: number) => get<PatchDetail>(`/api/patches/${id}`),
  patchImpact: (id: number) => get<PatchImpact>(`/api/patches/${id}/impact`),
  heroes: () => get<Hero[]>('/api/heroes'),
  hero: (id: number) => get<HeroDetail>(`/api/heroes/${id}`),
  items: () => get<Item[]>('/api/items'),
  item: (id: number) => get<ItemDetail>(`/api/items/${id}`),
}

export const health = () => get<Health>('/health')

export const meApi = {
  me: () => get<Me>('/api/me'),
  sync: async () => {
    const resp = await fetch(`${BASE}/api/me/sync`, { method: 'POST', credentials: 'include' })
    if (!resp.ok) throw new Error(`sync -> ${resp.status}`)
    return resp.json() as Promise<SyncResult>
  },
  analytics: () => get<MyAnalytics>('/api/me/analytics'),
  patchImpact: () => get<MyPatchImpact>('/api/me/patch-impact'),
  matches: () => get<MyMatch[]>('/api/me/matches?limit=30'),
}
