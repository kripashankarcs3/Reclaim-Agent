import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev server hamesha EK hi fixed address pe chale, taaki purana/stale UI na dikhe:
// - strictPort: agar 5173 pe pehle se koi (purana) server hai to Vite chupchaap
//   5174 pe shift NAHI hoga — error dega. Warna browser purane server ka UI dikhata.
// - no-store header: browser kabhi cached purana page/asset na dikhaye.
const devServer = {
  host: '127.0.0.1',
  port: 5173,
  strictPort: true,
  headers: { 'Cache-Control': 'no-store' },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: devServer,
  preview: { ...devServer, port: 4173 },
})
