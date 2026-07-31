/**
 * Coin detail: current price, 24-hour movement, the user's position in the
 * asset, and a 24-hour price chart.
 */

import { ChevronLeftIcon } from '@chakra-ui/icons'
import {
  Box,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  Heading,
  HStack,
  SimpleGrid,
  Skeleton,
  Stack,
  Tag,
  Text,
  VisuallyHidden,
} from '@chakra-ui/react'
import { Link as RouterLink, useParams } from 'react-router-dom'

import AssetBadge from '../components/common/AssetBadge'
import ChangeIndicator from '../components/common/ChangeIndicator'
import MetricTile from '../components/common/MetricTile'
import PriceChart from '../components/common/PriceChart'
import SectionCard from '../components/common/SectionCard'
import StatePanel from '../components/common/StatePanel'
import { useCoin } from '../hooks/usePortfolio'
import { assetName } from '../lib/assets'
import {
  formatAmount,
  formatCurrency,
  formatCurrencyDelta,
  formatPercent,
  formatTimestamp,
} from '../lib/format'

export function CoinPage() {
  const params = useParams<{ currency: string }>()
  const currency = (params.currency ?? '').toUpperCase()

  const coin = useCoin(currency)
  const name = assetName(currency)

  const priceDelta =
    coin.price != null && coin.price24hAgo != null ? coin.price - coin.price24hAgo : null

  const liveMessage =
    coin.isPriceLoading || coin.priceErrorMessage
      ? ''
      : `${currency} price ${formatCurrency(coin.price)}, ${formatPercent(coin.change24h)} over the last 24 hours.`

  return (
    <Stack spacing={{ base: 5, md: 7 }}>
      <Box>
        <Breadcrumb
          spacing={2}
          separator={<ChevronLeftIcon transform="rotate(180deg)" color="fg.subtle" />}
          fontSize="sm"
          mb={3}
        >
          <BreadcrumbItem>
            <BreadcrumbLink as={RouterLink} to="/">
              Dashboard
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbItem isCurrentPage>
            <Text color="fg.muted">{currency}</Text>
          </BreadcrumbItem>
        </Breadcrumb>

        <HStack spacing={4} align="center">
          <AssetBadge currency={currency} size="md" />
          <Box>
            <Heading as="h1" size="lg">
              {name ? `${name} (${currency})` : currency}
            </Heading>
            <HStack mt={1.5} spacing={2}>
              <Text color="fg.muted" fontSize="sm">
                Priced in GBP
              </Text>
              {coin.isCash && (
                <Tag size="sm" bg="bg.subtle" color="fg.muted" borderRadius="full">
                  Cash balance
                </Tag>
              )}
            </HStack>
          </Box>
        </HStack>
      </Box>

      {coin.priceErrorMessage ? (
        <StatePanel
          tone="error"
          title={`We couldn't price ${currency}`}
          description={coin.priceErrorMessage}
          actionLabel="Try again"
          onAction={coin.refetch}
          data-testid="coin-price-error"
        />
      ) : (
        <>
          <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} spacing={{ base: 3, md: 4 }}>
            <MetricTile
              label="Current price"
              emphasis="strong"
              isLoading={coin.isPriceLoading}
              value={formatCurrency(coin.price)}
              data-testid="coin-price"
              footnote={
                <ChangeIndicator
                  percent={coin.change24h}
                  secondary={formatCurrencyDelta(priceDelta)}
                  srSuffix="over the last 24 hours"
                />
              }
            />
            <MetricTile
              label="Price 24h ago"
              isLoading={coin.isPriceLoading}
              value={formatCurrency(coin.price24hAgo)}
              footnote={
                <Text fontSize="xs" color="fg.muted">
                  {coin.priceTime ? `As of ${formatTimestamp(coin.priceTime)}` : '—'}
                </Text>
              }
            />
            <MetricTile
              label="Your balance"
              isLoading={coin.isHoldingLoading}
              value={
                coin.isUnknownHolding ? '—' : `${formatAmount(coin.balance, currency)} ${currency}`
              }
              data-testid="coin-balance"
              footnote={
                <Text fontSize="xs" color="fg.muted">
                  {coin.isUnknownHolding ? 'Not held in this portfolio' : 'Held on Coinbase'}
                </Text>
              }
            />
            <MetricTile
              label="Holding value"
              isLoading={coin.isPriceLoading || coin.isHoldingLoading}
              value={coin.isUnknownHolding ? '—' : formatCurrency(coin.value)}
              data-testid="coin-value"
              footnote={
                <Text fontSize="xs" color="fg.muted">
                  Balance × current price
                </Text>
              }
            />
          </SimpleGrid>

          <VisuallyHidden role="status" aria-live="polite">
            {liveMessage}
          </VisuallyHidden>

          <SectionCard
            title="Last 24 hours"
            headingId="chart-heading"
            subtitle="Hourly closing price."
          >
            {coin.isCash ? (
              <StatePanel
                tone="empty"
                title="No price history for cash"
                description={`${currency} is a cash balance, so it has no market price history.`}
                data-testid="coin-chart-cash"
              />
            ) : coin.isHistoryError ? (
              <StatePanel
                tone="error"
                title="Price history is unavailable"
                description="The candle data couldn't be loaded. The figures above are still current."
                actionLabel="Try again"
                onAction={coin.refetch}
                data-testid="coin-chart-error"
              />
            ) : coin.isHistoryLoading ? (
              <Box data-testid="coin-chart-loading">
                <Skeleton height={{ base: '13rem', md: '17rem' }} borderRadius="md" />
                <Skeleton height="1.5rem" width="12rem" mt={3} />
              </Box>
            ) : coin.series.length === 0 ? (
              <StatePanel
                tone="empty"
                title="No price history yet"
                description="Coinbase returned no candles for this pair in the last 24 hours."
              />
            ) : (
              <PriceChart
                currency={currency}
                series={coin.series}
                change24h={coin.change24h}
              />
            )}
          </SectionCard>
        </>
      )}
    </Stack>
  )
}

export default CoinPage
