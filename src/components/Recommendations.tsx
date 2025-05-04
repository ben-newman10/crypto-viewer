import { Box, Card, CardBody, CardHeader, Heading, Text, Stack, useToast } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'

interface RecommendationResponse {
  recommendations: string
}

const Recommendations = () => {
  const toast = useToast()
  
  const { data, isLoading, error } = useQuery<RecommendationResponse>({
    queryKey: ['recommendations'],
    queryFn: async () => {
      const response = await fetch('/api/recommendations')
      if (!response.ok) {
        throw new Error('Failed to fetch recommendations')
      }
      return response.json()
    },
    refetchInterval: 5 * 60 * 1000, // Refresh every 5 minutes
    retry: 1,
    onError: (error) => {
      toast({
        title: 'Error fetching recommendations',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    }
  })

  if (isLoading) {
    return <Box>Loading recommendations...</Box>
  }

  if (error) {
    return (
      <Card bg="red.50">
        <CardBody>
          <Text color="red.500">Failed to load recommendations. Please try again later.</Text>
        </CardBody>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <Heading size="md">AI Recommendations</Heading>
      </CardHeader>
      <CardBody>
        <Stack spacing={4}>
          {data?.recommendations.split('\n').map((line, index) => (
            <Text key={index}>{line}</Text>
          ))}
        </Stack>
      </CardBody>
    </Card>
  )
}

export default Recommendations