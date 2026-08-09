/**
 * One asset's call: direction, confidence, why that confidence, and the
 * evidence it rests on.
 *
 * The confidence rating is deliberately at the top next to the direction, not
 * buried in the rationale text — a call and its confidence are one piece of
 * information, and separating them invites reading the first without the
 * second.
 */

import { Box, Divider, HStack, List, ListItem, Text, VisuallyHidden } from '@chakra-ui/react'

import type { AssetRecommendation } from '../../lib/api'
import AssetBadge from '../common/AssetBadge'
import { ActionBadge, ConfidenceBadge } from './badges'
import SupportingFacts from './SupportingFacts'

export interface RecommendationCardProps {
  recommendation: AssetRecommendation
}

export function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const {
    symbol,
    confidence,
    model_confidence: modelConfidence,
    confidence_ceiling: ceiling,
    ceiling_reason: ceilingReason,
    categories_missing: missing,
  } = recommendation

  // Worth calling out only when the data actually held the model back: an
  // agreeing pair of ratings needs no explanation.
  const wasCapped = modelConfidence !== confidence

  return (
    <Box
      as="article"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="lg"
      p={{ base: 3.5, md: 4 }}
      bg="bg.surface"
      data-testid="recommendation-card"
      data-symbol={symbol}
    >
      <HStack spacing={3} align="center" justify="space-between" flexWrap="wrap" rowGap={2}>
        <HStack spacing={2.5} minW={0}>
          <AssetBadge currency={symbol} />
          {/* h3 sits under the panel's own h2, keeping the outline ordered. */}
          <Text as="h3" fontSize="md" fontWeight={650} letterSpacing="-0.01em">
            {symbol}
          </Text>
        </HStack>
        <HStack spacing={2} flexWrap="wrap" rowGap={2}>
          <ActionBadge action={recommendation.recommendation} />
          <ConfidenceBadge confidence={confidence} />
        </HStack>
      </HStack>

      <Text mt={3} fontSize="sm" color="fg.default" data-testid="confidence-rationale">
        {recommendation.confidence_rationale}
      </Text>

      {wasCapped && (
        <Text mt={2} fontSize="xs" color="fg.muted" data-testid="confidence-capped">
          Lowered from {modelConfidence}: the ceiling for this pass is {ceiling} — {ceilingReason}.
          {missing.length > 0 && ` Missing: ${missing.join(', ')}.`}
        </Text>
      )}

      {recommendation.verification_note && (
        <Text mt={2} fontSize="xs" color="warning.fg" data-testid="verification-note">
          {recommendation.verification_note}
        </Text>
      )}

      <SupportingFacts symbol={symbol} facts={recommendation.supporting_facts} />

      {recommendation.risks_or_caveats.length > 0 && (
        <>
          <Divider my={3} borderColor="border.subtle" />
          <Text fontSize="xs" fontWeight={600} color="fg.muted" textTransform="uppercase" letterSpacing="0.04em">
            What would change this
          </Text>
          <List mt={1.5} spacing={1} fontSize="sm" color="fg.muted" styleType="disc" pl={4}>
            {recommendation.risks_or_caveats.map((risk) => (
              <ListItem key={risk} data-testid="risk-item">
                {risk}
              </ListItem>
            ))}
          </List>
        </>
      )}

      <VisuallyHidden>
        Grounding data completeness for {symbol}:{' '}
        {Math.round(recommendation.data_completeness * 100)} per cent.
      </VisuallyHidden>
    </Box>
  )
}

export default RecommendationCard
