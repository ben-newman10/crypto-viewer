/**
 * Portfolio panel: headline figures plus the holdings list.
 *
 * Handles all four async states explicitly — first load (skeletons), failure
 * (retryable error panel), no holdings (empty state) and no search matches —
 * so the user never sees a blank region.
 */

import { RepeatIcon, SearchIcon } from '@chakra-ui/icons'
import {
  Box,
  Button,
  Input,
  InputGroup,
  InputLeftElement,
  VisuallyHidden,
} from '@chakra-ui/react'
import { useMemo, useState } from 'react'

import { usePortfolio } from '../hooks/usePortfolio'
import SectionCard from './common/SectionCard'
import StatePanel from './common/StatePanel'
import HoldingsCards from './portfolio/HoldingsCards'
import HoldingsTable from './portfolio/HoldingsTable'
import {
  DEFAULT_SORT,
  filterHoldings,
  nextSortState,
  sortHoldings,
  type SortKey,
  type SortState,
} from './portfolio/sorting'

const Portfolio = () => {
  const { holdings, isInitialLoading, isError, isEmpty, refetch, isRefetching } =
    usePortfolio()

  const [sort, setSort] = useState<SortState>(DEFAULT_SORT)
  const [query, setQuery] = useState('')

  const visible = useMemo(
    () => sortHoldings(filterHoldings(holdings, query), sort),
    [holdings, query, sort],
  )

  const handleSort = (key: SortKey) => setSort((current) => nextSortState(current, key))

  const body = () => {
    if (isError) {
      return (
        <Box px={{ base: 4, md: 6 }} py={{ base: 4, md: 6 }}>
          <StatePanel
            tone="error"
            title="We couldn't load your portfolio"
            description="The Coinbase connection failed. Your balances are safe — this is a read-only view."
            actionLabel="Try again"
            onAction={() => void refetch()}
            isActionLoading={isRefetching}
            data-testid="portfolio-error"
          />
        </Box>
      )
    }

    if (isEmpty) {
      return (
        <Box px={{ base: 4, md: 6 }} py={{ base: 4, md: 6 }}>
          <StatePanel
            tone="empty"
            title="No holdings yet"
            description="Once you hold a balance on Coinbase it will appear here, priced in GBP."
            actionLabel="Refresh"
            onAction={() => void refetch()}
            isActionLoading={isRefetching}
            data-testid="portfolio-empty"
          />
        </Box>
      )
    }

    if (!isInitialLoading && visible.length === 0) {
      return (
        <Box px={{ base: 4, md: 6 }} py={{ base: 4, md: 6 }}>
          <StatePanel
            tone="empty"
            title={`No assets match “${query.trim()}”`}
            description="Try a different ticker, or clear the filter to see everything."
            actionLabel="Clear filter"
            onAction={() => setQuery('')}
            data-testid="portfolio-no-matches"
          />
        </Box>
      )
    }

    return (
      <>
        {/* Table on tablet and up, stacked cards on mobile. */}
        <Box display={{ base: 'none', md: 'block' }}>
          <HoldingsTable
            holdings={visible}
            sort={sort}
            onSort={handleSort}
            isLoading={isInitialLoading}
          />
        </Box>
        <Box display={{ base: 'block', md: 'none' }}>
          <HoldingsCards holdings={visible} isLoading={isInitialLoading} />
        </Box>
      </>
    )
  }

  return (
    <SectionCard
      title="Holdings"
      headingId="holdings-heading"
      subtitle="Balances priced in GBP, refreshed every 30 seconds."
      flushBody
      actions={
        <>
          {/* Nothing to filter when the list is unavailable or empty. */}
          <Box w={{ base: '100%', sm: '11rem' }} hidden={isError || isEmpty}>
            {/* Visually hidden, but a real <label> bound to the input. */}
            <VisuallyHidden as="label" htmlFor="holdings-filter">
              Filter holdings by ticker
            </VisuallyHidden>
            <InputGroup size="sm">
              <InputLeftElement pointerEvents="none">
                <SearchIcon boxSize={3} color="fg.subtle" aria-hidden="true" />
              </InputLeftElement>
              <Input
                id="holdings-filter"
                placeholder="Filter by ticker"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                borderRadius="md"
              />
            </InputGroup>
          </Box>

          <Button
            variant="outline"
            size="sm"
            leftIcon={<RepeatIcon aria-hidden="true" />}
            onClick={() => void refetch()}
            isLoading={isRefetching}
            loadingText="Refreshing"
            flexShrink={0}
          >
            Refresh
          </Button>
        </>
      }
    >
      {body()}
    </SectionCard>
  )
}

export default Portfolio
