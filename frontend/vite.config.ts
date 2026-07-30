/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test-setup.ts',
    globals: true,
    // Playwright's own e2e/*.spec.ts files use @playwright/test's test()/expect(),
    // not vitest's — without this exclusion vitest's default glob picks them up too
    // and fails immediately (different, incompatible test-runner APIs). Setting
    // `exclude` replaces vitest's own defaults rather than adding to them, so they're
    // repeated here alongside e2e/ rather than silently dropped.
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/cypress/**',
      '**/.{idea,git,cache,output,temp}/**',
      '**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build}.config.*',
      'e2e/**',
    ],
  },
})
