/**
 * Headline portfolio figures.
 *
 * Reads from the same React Query cache as the holdings panel, so mounting it
 * separately costs no extra requests. The figures refresh on a 30-second poll,
 * and a polite live region announces the new total to screen-reader users
 * without moving focus.
 */

import { SimpleGrid, Text, VisuallyHidden } from '@chakra-ui/react'

import { usePortfolio } from '../../hooks/usePortfolio'
import {
  directionOf,
  formatCurrency,
  formatCurrencyDelta,
  formatPercent,
  formatTimestamp,
} from '../../lib/format'
import ChangeIndicator from '../common/ChangeIndicator'
import MetricTile from '../common/MetricTile'

export function PortfolioSummary() {
  const { totals, isInitialLoading, isError, isEmpty } = usePortfolio()

  const direction = directionOf(totals.changePercent)
  const word = direction === 'up' ? 'up' : direction === 'down' ? 'down' : 'unchanged'

  const liveMessage =
    isInitialLoading || isError
      ? ''
      : `Portfolio value ${formatCurrency(totals.totalValue)}, ${word} ` +
        `${formatPercent(totals.changePercent)} over the last 24 hours.`

  // With no data to summarise, the tiles would render a misleading £0.00.
  if (isError) return null

  return (
    <>
      <SimpleGrid columns={{ base: 1, sm: 2, md: 3 }} spacing={{ base: 3, md: 4 }}>
        <MetricTile
          label="Total value"
          emphasis="strong"
          isLoading={isInitialLoading}
          value={formatCurrency(totals.totalValue)}
          data-testid="metric-total-value"
          footnote={
            <ChangeIndicator
              percent={totals.changePercent}
              size="md"
              srSuffix="over the last 24 hours"
            />
          }
        />

        <MetricTile
          label="24-hour change"
          isLoading={isInitialLoading}
          value={formatCurrencyDelta(totals.delta)}
          data-testid="metric-change"
          footnote={
            <Text fontSize="xs" color="fg.muted">
              {isEmpty
                ? 'No holdings to value'
                : `From ${formatCurrency(totals.total24hAgo)} yesterday`}
            </Text>
          }
        />

        <MetricTile
          label="Assets tracked"
          isLoading={isInitialLoading}
          value={String(totals.assetCount)}
          data-testid="metric-assets"
          footnote={
            <Text fontSize="xs" color={totals.hasPriceErrors ? 'warning.fg' : 'fg.muted'}>
              {totals.hasPriceErrors
                ? `${totals.pricedCount} priced · some prices unavailable`
                : totals.asOf
                  ? `Priced ${formatTimestamp(totals.asOf)}`
                  : 'Awaiting prices'}
            </Text>
          }
        />
      </SimpleGrid>

      <VisuallyHidden role="status" aria-live="polite">
        {liveMessage}
      </VisuallyHidden>
    </>
  )
}

export default PortfolioSummary
