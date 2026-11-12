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

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(path)
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

export const meApi = {
  me: () => get<Me>('/api/me'),
  sync: async () => {
    const resp = await fetch('/api/me/sync', { method: 'POST' })
    if (!resp.ok) throw new Error(`sync -> ${resp.status}`)
    return resp.json() as Promise<SyncResult>
  },
  analytics: () => get<MyAnalytics>('/api/me/analytics'),
  patchImpact: () => get<MyPatchImpact>('/api/me/patch-impact'),
  matches: () => get<MyMatch[]>('/api/me/matches?limit=30'),
}
