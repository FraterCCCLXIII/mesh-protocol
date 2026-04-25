import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  /** Pre-bundle Radix + avoid stale chunks after dep or lockfile changes (504 Outdated Optimize Dep). */
  optimizeDeps: {
    include: [
      '@radix-ui/react-dialog',
      '@radix-ui/react-dropdown-menu',
      '@radix-ui/react-label',
      '@radix-ui/react-radio-group',
      '@radix-ui/react-scroll-area',
      '@radix-ui/react-switch',
      '@radix-ui/react-tabs',
    ],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
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
