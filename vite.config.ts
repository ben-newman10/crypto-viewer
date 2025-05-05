/**
 * Vite configuration for the Crypto Viewer frontend.
 * Configures build settings, development server, and plugins.
 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Enable React plugin for JSX support and Fast Refresh
  plugins: [react()],
  
  // Development server configuration
  server: {
    // Configure proxy for API requests during development
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
        secure: false,
      },
    },
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
          'react-vendor': ['react', 'react-dom'],
          'chart-vendor': ['chart.js', 'react-chartjs-2'],
          'ui-vendor': ['@chakra-ui/react', '@emotion/react', '@emotion/styled']
        }
      }
    }
  }
})
