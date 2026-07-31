/**
 * Dashboard: portfolio figures across the top, then holdings alongside the AI
 * analysis panel.
 */

import { Box, Grid, GridItem, Heading, Stack, Text } from '@chakra-ui/react'

import Portfolio from '../components/Portfolio'
import PortfolioSummary from '../components/portfolio/PortfolioSummary'
import Recommendations from '../components/Recommendations'

export function DashboardPage() {
  return (
    <Stack spacing={{ base: 5, md: 6 }}>
      <Box>
        <Heading as="h1" size="lg">
          Your portfolio
        </Heading>
        <Text mt={1.5} color="fg.muted" fontSize="sm" maxW="42rem">
          Live balances and prices from Coinbase, with model-generated commentary on your
          current positions.
        </Text>
      </Box>

      <PortfolioSummary />

      <Grid
        templateColumns={{ base: '1fr', xl: 'minmax(0, 1.6fr) minmax(21rem, 1fr)' }}
        gap={{ base: 5, md: 6 }}
        alignItems="start"
      >
        <GridItem minW={0}>
          <Portfolio />
        </GridItem>
        <GridItem minW={0}>
          <Recommendations />
        </GridItem>
      </Grid>
    </Stack>
  )
}

export default DashboardPage
