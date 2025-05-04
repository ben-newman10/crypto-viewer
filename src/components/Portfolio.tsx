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

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

interface CryptoHolding {
  currency: string
  balance: string
  available: string
}

const Portfolio = () => {
  const { data: portfolio, isLoading } = useQuery<CryptoHolding[]>({
    queryKey: ['portfolio'],
    queryFn: async () => {
      const response = await fetch('/api/crypto/portfolio')
      return response.json()
    },
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  const { data: prices } = useQuery({
    queryKey: ['prices', portfolio],
    enabled: !!portfolio,
    queryFn: async () => {
      const pricePromises = portfolio!.map(async (holding) => {
        const response = await fetch(`/api/crypto/price/${holding.currency}-GBP`)
        return response.json()
      })
      return Promise.all(pricePromises)
    },
    refetchInterval: 10000 // Refresh prices every 10 seconds
  })

  if (isLoading) {
    return <Box>Loading portfolio...</Box>
  }

  return (
    <Stack spacing={4}>
      <Heading size="lg">Your Crypto Portfolio</Heading>
      <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' }} gap={4}>
        {portfolio?.map((holding, index) => (
          <Card key={holding.currency}>
            <CardBody>
              <Stat>
                <StatLabel>{holding.currency}</StatLabel>
                <StatNumber>{Number(holding.balance).toFixed(4)}</StatNumber>
                {prices?.[index] && (
                  <Text color="gray.600">
                    £{(Number(holding.balance) * Number(prices[index].price)).toFixed(2)} GBP
                    <StatArrow type={Number(prices[index].price) > 0 ? 'increase' : 'decrease'} />
                  </Text>
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