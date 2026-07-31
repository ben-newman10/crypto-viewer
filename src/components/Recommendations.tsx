/**
 * AI analysis panel.
 *
 * Renders structured, verified recommendations: a portfolio summary, one card
 * per holding with its confidence rating and evidence, and the disclaimer the
 * server attached to the payload.
 *
 * The result region is a polite live region so screen-reader users are told
 * when new analysis lands, and failures render an in-place retry rather than a
 * transient toast.
 */

import { InfoOutlineIcon, RepeatIcon } from '@chakra-ui/icons'
import {
  Box,
  Button,
  HStack,
  Icon,
  Skeleton,
  SkeletonText,
  Stack,
  Text,
  VisuallyHidden,
} from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown, { type Components } from 'react-markdown'

import { api, type RecommendationResponse } from '../lib/api'
import SectionCard from './common/SectionCard'
import StatePanel from './common/StatePanel'
import RecommendationCard from './recommendations/RecommendationCard'

/** AI analysis is expensive to generate, so it refreshes far less often. */
const REFRESH_INTERVAL_MS = 15 * 60 * 1000

/**
 * The panel heading is an `<h2>`, so markdown headings are shifted down a level
 * to keep the document outline ordered (no skipped levels).
 */
const MARKDOWN_COMPONENTS: Components = {
  h1: ({ children }) => <h3>{children}</h3>,
  h2: ({ children }) => <h3>{children}</h3>,
  h3: ({ children }) => <h4>{children}</h4>,
  h4: ({ children }) => <h5>{children}</h5>,
  // Keep external links safe and predictable.
  a: ({ children, href }) => (
    <a href={href} rel="noreferrer noopener" target="_blank">
      {children}
    </a>
  ),
}

function LoadingBody() {
  return (
    <Stack spacing={4} data-testid="recommendations-loading" aria-hidden="true">
      <Skeleton height="1.1rem" width="40%" />
      <SkeletonText noOfLines={3} spacing={3} skeletonHeight="0.7rem" />
      <Skeleton height="1.1rem" width="55%" />
      <SkeletonText noOfLines={4} spacing={3} skeletonHeight="0.7rem" />
    </Stack>
  )
}

/**
 * The disclaimer sits with the calls themselves, not in a page footer: it is
 * part of reading a recommendation, and a footer is the one place a reader
 * scrolling through cards will never look.
 */
function Disclaimer({ text }: { text: string }) {
  return (
    <HStack
      as="p"
      align="flex-start"
      spacing={2}
      mt={4}
      p={3}
      borderRadius="md"
      borderWidth="1px"
      borderColor="border.subtle"
      bg="bg.subtle"
      data-testid="recommendations-disclaimer"
    >
      <Icon as={InfoOutlineIcon} boxSize={3.5} mt={0.5} color="fg.muted" aria-hidden="true" />
      <Text as="span" fontSize="xs" color="fg.muted">
        {text}
      </Text>
    </HStack>
  )
}

/** Summary of what the verification step had to do, when it had to do anything. */
function GroundednessNote({ data }: { data: RecommendationResponse }) {
  const { groundedness } = data
  if (groundedness.status === 'verified') {
    return (
      <Text mt={3} fontSize="xs" color="fg.subtle" data-testid="groundedness-note">
        All {groundedness.facts_checked} supporting figures were checked against the data
        the app fetched.
      </Text>
    )
  }

  return (
    <Text mt={3} fontSize="xs" color="warning.fg" data-testid="groundedness-note">
      {groundedness.facts_corrected} figure(s) were corrected and {groundedness.facts_dropped}{' '}
      unverifiable claim(s) removed after checking against the data the app fetched
      {groundedness.retried ? ', following one regeneration' : ''}. Affected confidence
      ratings were lowered.
    </Text>
  )
}

const Recommendations = () => {
  const { data, isPending, isError, refetch, isRefetching } = useQuery<RecommendationResponse>({
    queryKey: ['recommendations'],
    queryFn: api.getRecommendations,
    refetchInterval: REFRESH_INTERVAL_MS,
  })

  const isBusy = isPending || isRefetching

  return (
    <SectionCard
      title="AI analysis"
      headingId="recommendations-heading"
      subtitle="Grounded in your holdings and the market data below — every figure is checked before it is shown."
      actions={
        <Button
          variant="outline"
          size="sm"
          leftIcon={<RepeatIcon aria-hidden="true" />}
          onClick={() => void refetch()}
          isLoading={isRefetching}
          loadingText="Analysing"
          data-testid="recommendations-refresh"
        >
          Refresh analysis
        </Button>
      }
    >
      {/*
        A single polite live region wraps every state so that the transition
        from "analysing" to a finished result is announced exactly once.
      */}
      <Box aria-live="polite" aria-busy={isBusy} data-testid="recommendations-region">
        {isPending ? (
          <>
            <LoadingBody />
            <VisuallyHidden>Generating analysis, please wait.</VisuallyHidden>
          </>
        ) : isError ? (
          <StatePanel
            tone="error"
            title="Analysis is unavailable"
            description="The analysis service didn't respond. Your balances above are unaffected."
            actionLabel="Try again"
            onAction={() => void refetch()}
            isActionLoading={isRefetching}
            data-testid="recommendations-error"
          />
        ) : (
          <Box data-testid="recommendations-content">
            {data && data.status !== 'ok' ? (
              // Nothing to analyse, or the model is unreachable while the
              // portfolio data is still good: say so in place, rather than
              // blanking the panel or raising an error.
              <Text fontSize="sm" color="fg.muted" data-testid="recommendations-message">
                {data.message}
              </Text>
            ) : (
              <>
                {data?.summary && (
                  <Box className="markdown-content" data-testid="recommendations-summary">
                    <ReactMarkdown components={MARKDOWN_COMPONENTS}>{data.summary}</ReactMarkdown>
                  </Box>
                )}

                <Stack spacing={3} mt={4}>
                  {data?.recommendations.map((recommendation) => (
                    <RecommendationCard
                      key={recommendation.symbol}
                      recommendation={recommendation}
                    />
                  ))}
                </Stack>

                {data && <GroundednessNote data={data} />}
              </>
            )}

            {data?.disclaimer && <Disclaimer text={data.disclaimer} />}
          </Box>
        )}
      </Box>
    </SectionCard>
  )
}

export default Recommendations
