# Deploying PatchIntel — 100% free tier

| Piece | Host | Cost |
|---|---|---|
| Backend API | Render free web service | $0 (sleeps when idle) |
| Database | Neon free Postgres (0.5 GB) | $0 |
| Pipeline cron | GitHub Actions (public repo) | $0 |
| Frontend | Vercel free | $0 |

Do these in order. ~20 minutes total.

---

## 1. Neon (database) — ~3 min

1. Go to [neon.tech](https://neon.tech) → sign up with GitHub.
2. Create a project (any name, e.g. `patchintel`). Default settings are fine.
3. On the project dashboard, copy the **connection string** (looks like
   `postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/patchintel?sslmode=require`).
4. **Edit it**: change the prefix `postgresql://` to `postgresql+psycopg://`
   (SQLAlchemy needs the driver name). Keep the rest exactly as-is.

Keep this string handy — you paste it in three places.

## 2. Render (backend) — ~8 min

1. Go to [render.com](https://render.com) → sign up with GitHub.
2. **New → Blueprint** → select the `patchintel` repo. Render reads
   `render.yaml` and shows one service (`patchintel-api`).
3. It will ask for the `sync: false` env vars — fill in:
   - `DATABASE_URL` → your edited Neon string
   - `STEAM_API_KEY` → your Steam key
   - `OPENAI_API_KEY` → your OpenAI key (or leave blank)
   - `APP_BASE_URL` → `https://patchintel-api.onrender.com` (adjust if Render
     gives you a different name — check the URL after deploy)
   - `CORS_ORIGINS` → leave blank for now; come back after step 3 with your
     Vercel URL
4. Deploy. When it's live, open `https://<your-app>.onrender.com/health` —
   you should see `"demo_mode": true`.
5. **Seed the demo data once** (so the site works before the first real
   ingest): Render dashboard → your service → **Shell** tab → run
   `python ../scripts/seed_demo.py`. (If Shell isn't available on the free
   plan, skip — the GitHub Action in step 4 will populate real data anyway.)

## 3. Vercel (frontend) — ~5 min

1. Go to [vercel.com](https://vercel.com) → sign up with GitHub →
   **Add New → Project** → import `patchintel`.
2. Set **Root Directory** to `frontend` (it auto-detects Vite).
3. Add environment variable:
   - `VITE_API_BASE` = `https://<your-app>.onrender.com` (no trailing slash)
4. Deploy. Open the Vercel URL — the demo banner should show and the patch
   pages should load.
5. Back in Render → your service → Environment → set `CORS_ORIGINS` to your
   Vercel URL (e.g. `https://patchintel.vercel.app`), save (it redeploys).

## 4. GitHub Actions (pipeline cron) — ~4 min

1. GitHub repo → **Settings → Secrets and variables → Actions → New repository
   secret**. Add:
   - `DATABASE_URL` → your edited Neon string
   - `STEAM_API_KEY` → your Steam key
   - optionally `OPENAI_API_KEY` and `DEADLOCK_API_KEY`
2. **Actions tab → pipeline → Run workflow** (manual first run). Watch it go
   green. From then on it runs every 6 hours.
3. After the first successful run, flip Render's `DEMO_MODE` to `"false"`.

## 5. Steam login in production

The dashboard sign-in uses `APP_BASE_URL` as the OpenID realm — verify it
matches your actual Render URL exactly (including `https://`, no trailing
slash). Steam sign-in should round-trip back to `/dashboard` on the Vercel
site.

---

### Troubleshooting

- **Health check returns 502 / deploy fails**: check Render logs — usually a
  malformed `DATABASE_URL` (missing `+psycopg`).
- **Frontend loads but no data**: `VITE_API_BASE` wrong, or `CORS_ORIGINS`
  on Render doesn't include the Vercel origin (must match exactly).
- **Steam login fails**: `APP_BASE_URL` mismatch with the real Render URL.
- **Pipeline Action fails on `alembic upgrade head`**: Neon string wrong or
  Neon project suspended (free projects suspend after inactivity — wake it
  from the Neon dashboard).
