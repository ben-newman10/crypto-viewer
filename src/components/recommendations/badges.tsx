/**
 * Badges for a recommendation's direction and confidence.
 *
 * Both follow the same rule as the gain/loss indicators elsewhere in the app:
 * the meaning is carried by an icon, a word and a colour together, never by
 * colour alone (WCAG 1.4.1). Every colour is a semantic token whose `*.fg` is
 * chosen to clear 4.5:1 on its own `*.subtle` background in both themes.
 */

import {
  CheckCircleIcon,
  MinusIcon,
  QuestionOutlineIcon,
  TriangleDownIcon,
  TriangleUpIcon,
  WarningIcon,
} from '@chakra-ui/icons'
import { HStack, Icon, Text } from '@chakra-ui/react'
import type { ComponentType } from 'react'

import type { Confidence, RecommendationAction } from '../../lib/api'

interface BadgeTokens {
  fg: string
  bg: string
  icon: ComponentType
  label: string
}

const ACTION_TOKENS: Record<RecommendationAction, BadgeTokens> = {
  buy: { fg: 'gain.fg', bg: 'gain.subtle', icon: TriangleUpIcon, label: 'Buy' },
  sell: { fg: 'loss.fg', bg: 'loss.subtle', icon: TriangleDownIcon, label: 'Sell' },
  hold: { fg: 'neutral.fg', bg: 'neutral.subtle', icon: MinusIcon, label: 'Hold' },
}

const CONFIDENCE_TOKENS: Record<Confidence, BadgeTokens> = {
  high: { fg: 'gain.fg', bg: 'gain.subtle', icon: CheckCircleIcon, label: 'High' },
  medium: { fg: 'warning.fg', bg: 'warning.subtle', icon: WarningIcon, label: 'Medium' },
  low: { fg: 'neutral.fg', bg: 'neutral.subtle', icon: QuestionOutlineIcon, label: 'Low' },
}

interface BadgeProps {
  tokens: BadgeTokens
  /** Text appended after the label, e.g. "confidence". */
  suffix?: string
  'data-testid'?: string
  'data-value'?: string
}

function Badge({ tokens, suffix, ...rest }: BadgeProps) {
  return (
    <HStack
      as="span"
      spacing={1.5}
      px={2.5}
      py={1}
      borderRadius="full"
      bg={tokens.bg}
      color={tokens.fg}
      flexShrink={0}
      {...rest}
    >
      <Icon as={tokens.icon} boxSize={3} aria-hidden="true" />
      <Text as="span" fontSize="xs" fontWeight={700} letterSpacing="0.01em" whiteSpace="nowrap">
        {tokens.label}
        {suffix ? ` ${suffix}` : ''}
      </Text>
    </HStack>
  )
}

export function ActionBadge({ action }: { action: RecommendationAction }) {
  return (
    <Badge tokens={ACTION_TOKENS[action]} data-testid="action-badge" data-value={action} />
  )
}

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return (
    <Badge
      tokens={CONFIDENCE_TOKENS[confidence]}
      suffix="confidence"
      data-testid="confidence-badge"
      data-value={confidence}
    />
  )
}
