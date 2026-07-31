/**
 * Main entry point for the Crypto Viewer frontend application.
 * Bootstraps React and renders the root application component.
 */

import { ColorModeScript } from '@chakra-ui/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App.tsx'
import './index.css'
import theme from './theme'

// Create and render the root application in strict mode
// StrictMode enables additional development checks and warnings
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* Applies the stored colour mode before first paint to avoid a flash. */}
    <ColorModeScript initialColorMode={theme.config.initialColorMode} />
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
