import type {
  Hero,
  HeroDetail,
  Item,
  ItemDetail,
  PatchDetail,
  PatchImpact,
  PatchListItem,
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
