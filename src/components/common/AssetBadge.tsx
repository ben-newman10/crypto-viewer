/**
 * Ticker chip shown beside each asset name.
 *
 * Purely decorative: the ticker is always rendered as real text next to it, so
 * the badge is hidden from assistive technology.
 */

import { Box, Text } from '@chakra-ui/react'

/** Deterministic hue per ticker, so an asset keeps the same colour everywhere. */
function hueFor(symbol: string): number {
  let hash = 0
  for (let i = 0; i < symbol.length; i += 1) {
    hash = (hash * 31 + symbol.charCodeAt(i)) % 360
  }
  return hash
}

export interface AssetBadgeProps {
  currency: string
  size?: 'sm' | 'md'
}

export function AssetBadge({ currency, size = 'sm' }: AssetBadgeProps) {
  const hue = hueFor(currency.toUpperCase())
  // Explicit lengths rather than Chakra space tokens: the space scale has gaps
  // (there is no `11`), and a missing token silently degrades to pixels.
  const dimension = size === 'sm' ? '2rem' : '2.5rem'

  return (
    <Box
      aria-hidden="true"
      flexShrink={0}
      w={dimension}
      h={dimension}
      borderRadius="full"
      display="grid"
      placeItems="center"
      bg={`hsl(${hue} 72% 94%)`}
      color={`hsl(${hue} 65% 26%)`}
      borderWidth="1px"
      borderColor={`hsl(${hue} 60% 84%)`}
      _dark={{
        bg: `hsl(${hue} 45% 18%)`,
        color: `hsl(${hue} 70% 78%)`,
        borderColor: `hsl(${hue} 40% 30%)`,
      }}
    >
      <Text
        as="span"
        fontSize={size === 'sm' ? 'xs' : 'sm'}
        fontWeight={700}
        letterSpacing="-0.02em"
      >
        {currency.slice(0, 3).toUpperCase()}
      </Text>
    </Box>
  )
}

export default AssetBadge
