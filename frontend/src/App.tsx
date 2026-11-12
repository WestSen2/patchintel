import { Link, Route, Routes } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { health } from './api'
import PatchesPage from './pages/PatchesPage'
import PatchDetailPage from './pages/PatchDetailPage'
import HeroesPage from './pages/HeroesPage'
import HeroDetailPage from './pages/HeroDetailPage'
import ItemsPage from './pages/ItemsPage'
import ItemDetailPage from './pages/ItemDetailPage'
import DashboardPage from './pages/DashboardPage'

export default function App() {
  const { data: healthData } = useQuery({ queryKey: ['health'], queryFn: health, retry: false })
  return (
    <div className="min-h-screen">
      {healthData?.demo_mode && (
        <div className="bg-deco-gold text-deco-ink text-center text-xs py-1.5 font-semibold tracking-wide">
          DEMO MODE — stats on this deployment are fabricated sample data
        </div>
      )}
      <nav className="border-b border-line">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="deco-heading text-xl">
            PatchIntel
          </Link>
          <div className="flex gap-6 text-sm text-deco-cream/70">
            <Link to="/" className="hover:text-deco-gold transition-colors">Patches</Link>
            <Link to="/heroes" className="hover:text-deco-gold transition-colors">Heroes</Link>
            <Link to="/items" className="hover:text-deco-gold transition-colors">Items</Link>
            <Link to="/dashboard" className="hover:text-deco-gold transition-colors">Dashboard</Link>
          </div>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<PatchesPage />} />
          <Route path="/patches/:id" element={<PatchDetailPage />} />
          <Route path="/heroes" element={<HeroesPage />} />
          <Route path="/heroes/:id" element={<HeroDetailPage />} />
          <Route path="/items" element={<ItemsPage />} />
          <Route path="/items/:id" element={<ItemDetailPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </main>
      <footer className="max-w-6xl mx-auto px-6 py-6 text-xs text-deco-cream/40 border-t border-line">
        PatchIntel — did the patch actually work? Community project, not affiliated with Valve.
      </footer>
    </div>
  )
}
