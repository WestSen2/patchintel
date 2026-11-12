import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // backend: uvicorn app.main:app --reload (port 8000)
      '/api': 'http://localhost:8000',
    },
  },
})
