/**
 * AI analysis panel.
 *
 * Fetches model-generated commentary on the portfolio. The result region is a
 * polite live region so screen-reader users are told when new analysis lands,
 * and failures render an in-place retry rather than a transient toast.
 */

import { RepeatIcon } from '@chakra-ui/icons'
import { Box, Button, Skeleton, SkeletonText, Stack, Text, VisuallyHidden } from '@chakra-ui/react'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown, { type Components } from 'react-markdown'

import { api, type RecommendationResponse } from '../lib/api'
import SectionCard from './common/SectionCard'
import StatePanel from './common/StatePanel'

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

const Recommendations = () => {
  const { data, isPending, isError, refetch, isRefetching, dataUpdatedAt } =
    useQuery<RecommendationResponse>({
      queryKey: ['recommendations'],
      queryFn: api.getRecommendations,
      refetchInterval: REFRESH_INTERVAL_MS,
    })

  const isBusy = isPending || isRefetching

  return (
    <SectionCard
      title="AI analysis"
      headingId="recommendations-heading"
      subtitle="Generated from your current holdings and 24-hour market data."
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
          <>
            <Box className="markdown-content" data-testid="recommendations-content">
              <ReactMarkdown components={MARKDOWN_COMPONENTS}>
                {data?.recommendations ?? ''}
              </ReactMarkdown>
            </Box>
            {dataUpdatedAt > 0 && (
              <Text mt={4} fontSize="xs" color="fg.subtle">
                Analysis is informational only and is not financial advice.
              </Text>
            )}
          </>
        )}
      </Box>
    </SectionCard>
  )
}

export default Recommendations
