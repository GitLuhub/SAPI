/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/main.tsx',
        'src/**/*.d.ts',
        // Infraestructura: testeada via integración, no unitariamente
        'src/App.tsx',
        'src/api/**',
        'src/contexts/**',
        'src/components/**',
        'src/types/**',
        'src/hooks/index.ts',
      ],
      thresholds: { lines: 80, functions: 80, branches: 80 },
    },
  },
})
