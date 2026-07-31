/**
 * Main application component that sets up the core providers, routing and
 * layout.
 *
 * Chakra supplies the design system, React Query owns server state, and React
 * Router provides addressable pages (which the E2E suite navigates directly).
 */

import { ChakraProvider } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Route, Routes } from 'react-router-dom'

import AppShell from './components/layout/AppShell'
import CoinPage from './pages/CoinPage'
import DashboardPage from './pages/DashboardPage'
import NotFoundPage from './pages/NotFoundPage'
import theme from './theme'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // One retry smooths over a transient blip without leaving the user
      // staring at a spinner when the backend is genuinely down.
      retry: 1,
      retryDelay: 400,
      // Prices are polled on an interval; refetching on every focus change
      // just adds noise.
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
})

function App() {
  return (
    <ChakraProvider theme={theme}>
      <QueryClientProvider client={queryClient}>
        <AppShell>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/coin/:currency" element={<CoinPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AppShell>
      </QueryClientProvider>
    </ChakraProvider>
  )
}

export default App
