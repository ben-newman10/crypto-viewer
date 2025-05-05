/**
 * Portfolio component displays the user's cryptocurrency holdings and their current values.
 * Features real-time price updates and responsive grid layout.
 */

import { Box, Card, CardBody, Heading, Stack, Text, Stat, StatLabel, StatNumber, StatArrow, StatHelpText, Grid } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'

/**
 * Interface defining the structure of cryptocurrency holding data
 * received from the backend API
 */
interface CryptoHolding {
  currency: string    // The cryptocurrency symbol (e.g., 'BTC', 'ETH')
  balance: string     // The total balance of the holding
  available: string   // The available balance that can be traded
}

interface CryptoPrice {
  price: string       // Current price
  time: string       // Timestamp
  change_24h: number // 24-hour price change percentage
  price_24h_ago: string // Price 24 hours ago
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
  const { data: prices } = useQuery<CryptoPrice[]>({
    queryKey: ['prices', portfolio],
    enabled: !!portfolio, // Only fetch prices when portfolio data exists
    queryFn: async () => {
      const pricePromises = portfolio!.map(async (holding) => {
        const response = await fetch(`/api/crypto/price/${holding.currency}-GBP`)
        return response.json()
      })
      return Promise.all(pricePromises)
    },
    refetchInterval: 30000 // Refresh prices every 30 seconds
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
                    {/* Total value in GBP */}
                    <StatNumber>
                      £{(Number(holding.balance) * Number(prices[index].price)).toFixed(2)}
                    </StatNumber>
                    {/* Current price per coin */}
                    <Text color="gray.600" fontSize="sm">
                      Current Price: £{Number(prices[index].price).toFixed(2)}
                    </Text>
                    {/* 24h change with arrow */}
                    <StatHelpText>
                      <StatArrow type={prices[index].change_24h >= 0 ? 'increase' : 'decrease'} />
                      {Math.abs(prices[index].change_24h).toFixed(2)}%
                    </StatHelpText>
                    {/* Balance */}
                    <Text fontSize="sm" mt={1}>
                      Balance: {Number(holding.balance).toFixed(4)} {holding.currency}
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