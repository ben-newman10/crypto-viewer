import { ChakraProvider, Box, Grid, GridItem } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Portfolio from './components/Portfolio'
import Recommendations from './components/Recommendations'

const queryClient = new QueryClient()

function App() {
  return (
    <ChakraProvider>
      <QueryClientProvider client={queryClient}>
        <Box minH="100vh" bg="gray.50" p={4}>
          <Grid
            templateColumns={{ base: '1fr', lg: '2fr 1fr' }}
            gap={6}
            maxW="1400px"
            mx="auto"
          >
            <GridItem>
              <Portfolio />
            </GridItem>
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
