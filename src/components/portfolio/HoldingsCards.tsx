/**
 * Holdings presentation for narrow (mobile) viewports.
 *
 * A five-column table is unreadable at 375px, so the same data is laid out as a
 * stacked list. Only one of the two presentations is ever displayed, which also
 * keeps it out of the accessibility tree.
 */

import { WarningTwoIcon } from '@chakra-ui/icons'
import {
  Box,
  Flex,
  HStack,
  Icon,
  Link as ChakraLink,
  Skeleton,
  Stack,
  Tag,
  Text,
  VisuallyHidden,
} from '@chakra-ui/react'
import { Link as RouterLink } from 'react-router-dom'

import type { HoldingView } from '../../hooks/usePortfolio'
import { formatAmount, formatCurrency } from '../../lib/format'
import AssetBadge from '../common/AssetBadge'
import ChangeIndicator from '../common/ChangeIndicator'

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Flex justify="space-between" align="baseline" gap={3}>
      <Text fontSize="sm" color="fg.muted">
        {label}
      </Text>
      <Box fontSize="sm" className="tabular" textAlign="right">
        {value}
      </Box>
    </Flex>
  )
}

export interface HoldingsCardsProps {
  holdings: HoldingView[]
  isLoading?: boolean
  skeletonRows?: number
}

export function HoldingsCards({
  holdings,
  isLoading = false,
  skeletonRows = 3,
}: HoldingsCardsProps) {
  if (isLoading) {
    return (
      <Stack as="ul" listStyleType="none" spacing={3} px={4} py={4}>
        {Array.from({ length: skeletonRows }, (_, index) => (
          <Box
            as="li"
            key={`skeleton-${index}`}
            borderWidth="1px"
            borderColor="border.subtle"
            borderRadius="md"
            p={4}
            data-testid="holding-card-skeleton"
          >
            <Skeleton height="1.25rem" width="45%" />
            <Skeleton height="0.9rem" width="70%" mt={3} />
            <Skeleton height="0.9rem" width="60%" mt={2} />
          </Box>
        ))}
      </Stack>
    )
  }

  return (
    <Stack as="ul" listStyleType="none" spacing={3} px={4} py={4}>
      {holdings.map((holding) => (
        <Box
          as="li"
          key={holding.currency}
          borderWidth="1px"
          borderColor="border.subtle"
          borderRadius="md"
          p={4}
          bg="bg.surface"
          data-testid="holding-card"
          data-currency={holding.currency}
        >
          <Flex justify="space-between" align="flex-start" gap={3}>
            <HStack spacing={3} minW={0}>
              <AssetBadge currency={holding.currency} size="md" />
              <Box minW={0}>
                {holding.isCash ? (
                  <HStack spacing={2}>
                    <Text fontWeight={700}>{holding.currency}</Text>
                    <Tag size="sm" bg="bg.subtle" color="fg.muted" borderRadius="full">
                      Cash
                    </Tag>
                  </HStack>
                ) : (
                  <ChakraLink
                    as={RouterLink}
                    to={`/coin/${holding.currency}`}
                    fontWeight={700}
                    color="fg.default"
                    _hover={{ color: 'accent.fg' }}
                  >
                    {holding.currency}
                    <VisuallyHidden> — view price detail</VisuallyHidden>
                  </ChakraLink>
                )}
                <Text fontSize="xs" color="fg.muted" className="tabular">
                  {formatAmount(holding.balance, holding.currency)} {holding.currency}
                </Text>
              </Box>
            </HStack>

            <Box textAlign="right">
              <Text fontWeight={700} className="tabular">
                {formatCurrency(holding.value)}
              </Text>
              {!holding.isCash && (
                <ChangeIndicator
                  percent={holding.change24h}
                  size="sm"
                  srSuffix={`over the last 24 hours for ${holding.currency}`}
                />
              )}
            </Box>
          </Flex>

          <Stack spacing={1.5} mt={3} pt={3} borderTopWidth="1px" borderColor="border.subtle">
            <Row
              label="Price"
              value={
                holding.priceState === 'loading' ? (
                  <Skeleton height="1rem" width="4.5rem" ml="auto" />
                ) : holding.priceState === 'error' ? (
                  <HStack spacing={1.5} justify="flex-end" color="warning.fg">
                    <Icon as={WarningTwoIcon} boxSize={3} aria-hidden="true" />
                    <Text as="span" fontSize="sm">
                      Unavailable
                    </Text>
                  </HStack>
                ) : (
                  formatCurrency(holding.price)
                )
              }
            />
            <Row label="Available" value={formatAmount(holding.available, holding.currency)} />
          </Stack>
        </Box>
      ))}
    </Stack>
  )
}

export default HoldingsCards
