/**
 * Vite configuration for the Crypto Viewer frontend.
 * Configures build settings, development server, and plugins.
 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend origin that `/api` requests are proxied to. Overridable so the E2E
// suite can point at a backend started on its own port in test mode.
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:3001'

const proxy = {
  '/api': {
    target: apiTarget,
    changeOrigin: true,
    secure: false,
  },
}

export default defineConfig({
  // Enable React plugin for JSX support and Fast Refresh
  plugins: [react()],

  // Development server configuration
  server: {
    // Configure proxy for API requests during development
    proxy,
  },

  // The preview server mirrors the dev proxy so the production build can be
  // exercised against the same backend (this is what Playwright runs against).
  preview: {
    proxy,
  },

  // Build configuration
  build: {
    // Output directory for production build
    outDir: 'dist',

    // Enable source maps for debugging
    sourcemap: true,

    // Optimize dependencies during build
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'chart-vendor': ['chart.js', 'react-chartjs-2'],
          'ui-vendor': ['@chakra-ui/react', '@emotion/react', '@emotion/styled'],
        },
      },
    },
  },
})
