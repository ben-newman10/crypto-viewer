/**
 * Fallback route.
 */

import { Box, Button, Heading, Stack, Text } from '@chakra-ui/react'
import { Link as RouterLink } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <Stack spacing={4} maxW="32rem">
      <Box>
        <Heading as="h1" size="lg">
          Page not found
        </Heading>
        <Text mt={2} color="fg.muted">
          That page doesn't exist. Head back to your portfolio to pick up where you left off.
        </Text>
      </Box>
      <Button as={RouterLink} to="/" alignSelf="flex-start">
        Back to dashboard
      </Button>
    </Stack>
  )
}

export default NotFoundPage
