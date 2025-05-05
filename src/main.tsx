/**
 * Main entry point for the Crypto Viewer frontend application.
 * Bootstraps React and renders the root application component.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Create and render the root application in strict mode
// StrictMode enables additional development checks and warnings
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
