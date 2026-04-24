import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 12001,
    host: '0.0.0.0',
    allowedHosts: ['work-2-ffrrmkwydsqbsmix.prod-runtime.all-hands.dev', 'localhost'],
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:12000',
        changeOrigin: true,
      },
      '/.well-known': {
        target: process.env.VITE_API_URL || 'http://localhost:12000',
        changeOrigin: true,
      },
    },
  },
})
