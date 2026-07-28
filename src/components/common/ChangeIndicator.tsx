/**
 * Signed change display for gains and losses.
 *
 * Direction is conveyed three ways so it never depends on colour alone
 * (WCAG 1.4.1): a triangle icon, an explicit +/− sign, and a visually hidden
 * word for screen readers.
 */

import { MinusIcon, TriangleDownIcon, TriangleUpIcon } from '@chakra-ui/icons'
import { HStack, Text, VisuallyHidden } from '@chakra-ui/react'

import { directionOf, formatPercent, type Direction } from '../../lib/format'

const TOKENS: Record<Direction, { fg: string; icon: typeof TriangleUpIcon; word: string }> = {
  up: { fg: 'gain.fg', icon: TriangleUpIcon, word: 'up' },
  down: { fg: 'loss.fg', icon: TriangleDownIcon, word: 'down' },
  flat: { fg: 'neutral.fg', icon: MinusIcon, word: 'unchanged' },
}

export interface ChangeIndicatorProps {
  /** Percentage change, already expressed as a percentage (e.g. 2.34). */
  percent: number | null | undefined
  /** Optional secondary text, e.g. the change in money terms. */
  secondary?: string
  size?: 'sm' | 'md' | 'lg'
  /** Screen-reader context, e.g. "over the last 24 hours". */
  srSuffix?: string
}

const SIZES = {
  sm: { fontSize: 'xs', iconSize: 2.5 },
  md: { fontSize: 'sm', iconSize: 3 },
  lg: { fontSize: 'lg', iconSize: 3.5 },
} as const

export function ChangeIndicator({
  percent,
  secondary,
  size = 'md',
  srSuffix,
}: ChangeIndicatorProps) {
  const direction = directionOf(percent)
  const { fg, icon: Icon, word } = TOKENS[direction]
  const { fontSize, iconSize } = SIZES[size]

  if (percent == null || !Number.isFinite(percent)) {
    return (
      <Text fontSize={fontSize} color="fg.subtle">
        —
      </Text>
    )
  }

  return (
    <HStack spacing={1.5} color={fg} align="baseline" justify="flex-end">
      <Icon boxSize={iconSize} aria-hidden="true" flexShrink={0} />
      <Text as="span" className="tabular" fontSize={fontSize} fontWeight={600}>
        {formatPercent(percent)}
      </Text>
      <VisuallyHidden>
        {word}
        {srSuffix ? ` ${srSuffix}` : ''}
      </VisuallyHidden>
      {/*
        The secondary figure carries no opacity: fading the token colour drops
        12px text below 4.5:1 on a white card. Size alone sets the hierarchy.
      */}
      {secondary && (
        <Text as="span" className="tabular" fontSize="xs" color={fg}>
          {secondary}
        </Text>
      )}
    </HStack>
  )
}

export default ChangeIndicator
