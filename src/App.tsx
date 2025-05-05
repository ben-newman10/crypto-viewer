/**
 * Main application component that sets up the core providers and layout.
 * Uses ChakraUI for styling and React Query for data fetching/caching.
 */

import { ChakraProvider, Box, Grid, GridItem } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Portfolio from './components/Portfolio'
import Recommendations from './components/Recommendations'

// Initialize React Query client for managing server state and caching
const queryClient = new QueryClient()

function App() {
  return (
    // ChakraProvider enables the use of Chakra UI components and theme
    <ChakraProvider>
      {/* QueryClientProvider enables React Query hooks throughout the app */}
      <QueryClientProvider client={queryClient}>
        {/* Main layout container with responsive padding and background */}
        <Box minH="100vh" bg="gray.50" p={4}>
          {/* Responsive grid layout: single column on mobile, two columns on desktop */}
          <Grid
            templateColumns={{ base: '1fr', lg: '2fr 1fr' }}
            gap={6}
            maxW="1400px"
            mx="auto"
          >
            {/* Portfolio section takes up more space in desktop view */}
            <GridItem>
              <Portfolio />
            </GridItem>
            {/* Recommendations section takes up less space in desktop view */}
            <GridItem>
              <Recommendations />
            </GridItem>
          </Grid>
        </Box>
      </QueryClientProvider>
    </ChakraProvider>
  )
}

export default App
