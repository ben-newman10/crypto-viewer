/**
 * Headline figure tile used by the portfolio summary and coin detail header.
 */

import { Box, Skeleton, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'

export interface MetricTileProps {
  label: string
  /** Primary figure. Rendered with tabular figures so tiles align. */
  value: ReactNode
  /** Supporting line beneath the figure, e.g. a change indicator. */
  footnote?: ReactNode
  isLoading?: boolean
  emphasis?: 'default' | 'strong'
  'data-testid'?: string
}

export function MetricTile({
  label,
  value,
  footnote,
  isLoading = false,
  emphasis = 'default',
  'data-testid': testId,
}: MetricTileProps) {
  return (
    <Box
      bg="bg.surface"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="lg"
      px={{ base: 4, md: 5 }}
      py={{ base: 4, md: 5 }}
      boxShadow="xs"
      data-testid={testId}
    >
      <Text
        fontSize="xs"
        fontWeight={600}
        letterSpacing="0.04em"
        textTransform="uppercase"
        color="fg.muted"
      >
        {label}
      </Text>

      {isLoading ? (
        <Skeleton mt={2} height={emphasis === 'strong' ? '2.5rem' : '1.75rem'} width="70%" />
      ) : (
        <Text
          className="tabular"
          mt={1}
          fontWeight={650}
          letterSpacing="-0.02em"
          // Headline figures must not wrap: a currency amount split across two
          // lines is unreadable, so the scale stays inside the tile width.
          whiteSpace="nowrap"
          fontSize={
            emphasis === 'strong' ? { base: '2xl', xl: '3xl' } : { base: 'lg', md: 'xl' }
          }
          lineHeight={1.2}
        >
          {value}
        </Text>
      )}

      <Box mt={2} minH="1.25rem">
        {isLoading ? <Skeleton height="1rem" width="45%" /> : footnote}
      </Box>
    </Box>
  )
}

export default MetricTile
