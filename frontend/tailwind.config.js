/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Deadlock-inspired art-deco palette: deep ink green, aged gold, bone cream
        ink: '#10140f',
        panel: '#171d15',
        line: '#2a3325',
        deco: {
          gold: '#c9a86a',
          dim: '#8a7648',
          cream: '#e8dfc8',
          green: '#1c261d',
        },
        verdict: {
          worked: '#4ade80',
          backfired: '#f87171',
          unclear: '#fbbf24',
          shifted: '#c084fc',
          noeffect: '#9ca3af',
          insufficient: '#64748b',
        },
      },
      fontFamily: {
        display: ['Georgia', 'Times New Roman', 'serif'],
        body: ['system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
