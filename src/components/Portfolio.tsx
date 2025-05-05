/**
 * Portfolio component displays the user's cryptocurrency holdings and their current values.
 * Features real-time price updates and responsive grid layout.
 */

import { Box, Card, CardBody, Heading, Stack, Text, Stat, StatLabel, StatNumber, StatArrow, Grid } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'

// Register required Chart.js components for price history visualization
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

/**
 * Interface defining the structure of cryptocurrency holding data
 * received from the backend API
 */
interface CryptoHolding {
  currency: string    // The cryptocurrency symbol (e.g., 'BTC', 'ETH')
  balance: string     // The total balance of the holding
  available: string   // The available balance that can be traded
}

const Portfolio = () => {
  // Fetch portfolio data with automatic refresh every 30 seconds
  const { data: portfolio, isLoading } = useQuery<CryptoHolding[]>({
    queryKey: ['portfolio'],
    queryFn: async () => {
      const response = await fetch('/api/crypto/portfolio')
      return response.json()
    },
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  // Fetch real-time prices for each cryptocurrency in the portfolio
  const { data: prices } = useQuery({
    queryKey: ['prices', portfolio],
    enabled: !!portfolio, // Only fetch prices when portfolio data exists
    queryFn: async () => {
      const pricePromises = portfolio!.map(async (holding) => {
        const response = await fetch(`/api/crypto/price/${holding.currency}-GBP`)
        return response.json()
      })
      return Promise.all(pricePromises)
    },
    refetchInterval: 10000 // Refresh prices every 10 seconds
  })

  // Show loading state while fetching initial portfolio data
  if (isLoading) {
    return <Box>Loading portfolio...</Box>
  }

  return (
    <Stack spacing={4}>
      <Heading size="lg">Your Crypto Portfolio</Heading>
      {/* Responsive grid layout: 1 column on mobile, 2 on tablet, 3 on desktop */}
      <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' }} gap={4}>
        {portfolio?.map((holding, index) => (
          <Card key={holding.currency}>
            <CardBody>
              <Stat>
                <StatLabel>{holding.currency}</StatLabel>
                {prices?.[index] && (
                  <>
                    {/* Display GBP value as the main number */}
                    <StatNumber>£{(Number(holding.balance) * Number(prices[index].price)).toFixed(2)}</StatNumber>
                    {/* Display coin balance as secondary info */}
                    <Text color="gray.600">
                      {Number(holding.balance).toFixed(4)} {holding.currency}
                      <StatArrow type={Number(prices[index].price) > 0 ? 'increase' : 'decrease'} />
                    </Text>
                  </>
                )}
              </Stat>
            </CardBody>
          </Card>
        ))}
      </Grid>
    </Stack>
  )
}

export default Portfolio