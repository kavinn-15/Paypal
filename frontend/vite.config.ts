/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import fs from 'node:fs'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootEnvExists = fs.existsSync(path.resolve(__dirname, '..', '.env'))
const envDir = rootEnvExists ? path.resolve(__dirname, '..') : __dirname

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  envDir,
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          recharts: ['recharts'],
          icons: ['lucide-react'],
        },
      },
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
  }
})

