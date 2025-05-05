/**
 * Recommendations component fetches and displays AI-powered trading recommendations
 * based on the user's portfolio and current market conditions.
 */

import { Box, Card, CardBody, CardHeader, Heading, useToast } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'

/**
 * Interface defining the structure of recommendation data
 * received from the backend API
 */
interface RecommendationResponse {
  recommendations: string  // Markdown-formatted recommendations
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
      const data: RecommendationResponse = await response.json()
      return data
    },
    refetchInterval: 15 * 60 * 1000, // Refresh every 15 minutes
    retry: 1, // Only retry once on failure
  })

  // Show loading state while fetching recommendations
  if (isLoading) {
    return <Box>Loading recommendations...</Box>
  }

  // Show error card if recommendation fetch failed
  if (error) {
    toast({
      title: 'Error fetching recommendations',
      description: error instanceof Error ? error.message : 'Unknown error occurred',
      status: 'error',
      duration: 5000,
      isClosable: true,
    })

    return (
      <Card bg="red.50">
        <CardBody>
          <Box color="red.500">Failed to load recommendations. Please try again later.</Box>
        </CardBody>
      </Card>
    )
  }

  // Render recommendations in a card with markdown content
  return (
    <Card>
      <CardHeader>
        <Heading size="md">AI Recommendations</Heading>
      </CardHeader>
      <CardBody>
        <Box className="markdown-content">
          <ReactMarkdown>{data?.recommendations || ''}</ReactMarkdown>
        </Box>
      </CardBody>
    </Card>
  )
}

export default Recommendations