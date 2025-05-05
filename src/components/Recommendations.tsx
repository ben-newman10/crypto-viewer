/**
 * Recommendations component fetches and displays AI-powered trading recommendations
 * based on the user's portfolio and current market conditions.
 */

import { Box, Card, CardBody, CardHeader, Heading, Text, Stack, useToast } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'

/**
 * Interface defining the structure of recommendation data
 * received from the backend API
 */
interface RecommendationResponse {
  recommendations: string  // Newline-separated list of recommendations
}

const Recommendations = () => {
  // Initialize toast notifications for error handling
  const toast = useToast()
  
  // Fetch AI recommendations with automatic refresh every 5 minutes
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
    retry: 1, // Only retry once on failure
    onError: (error) => {
      // Show error toast when recommendation fetch fails
      toast({
        title: 'Error fetching recommendations',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    }
  })

  // Show loading state while fetching recommendations
  if (isLoading) {
    return <Box>Loading recommendations...</Box>
  }

  // Show error card if recommendation fetch failed
  if (error) {
    return (
      <Card bg="red.50">
        <CardBody>
          <Text color="red.500">Failed to load recommendations. Please try again later.</Text>
        </CardBody>
      </Card>
    )
  }

  // Render recommendations in a card with each line as a separate text element
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