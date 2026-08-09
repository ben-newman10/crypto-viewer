/**
 * The evidence behind a call, as a keyboard-reachable disclosure.
 *
 * Every entry names the exact grounding field the claim came from, so a reader
 * can trace any number back to the data the app fetched instead of taking the
 * headline on trust. That is what makes a recommendation inspectable — the
 * confidence badge on its own does not.
 *
 * Laid out as a list rather than a table: the panel sits in a narrow sidebar
 * column on the dashboard, where a three-column table either clips or forces a
 * horizontal scroll.
 */

import { ChevronDownIcon, ChevronRightIcon } from '@chakra-ui/icons'
import { Box, Button, Flex, List, ListItem, Text } from '@chakra-ui/react'
import { useId, useState } from 'react'

import type { SupportingFact } from '../../lib/api'

export interface SupportingFactsProps {
  symbol: string
  facts: SupportingFact[]
}

export function SupportingFacts({ symbol, facts }: SupportingFactsProps) {
  const [open, setOpen] = useState(false)
  const panelId = useId()

  if (facts.length === 0) {
    return (
      <Text mt={3} fontSize="sm" color="fg.muted" data-testid="supporting-facts-empty">
        No claim in this call could be traced to an available data field.
      </Text>
    )
  }

  return (
    <Box mt={3}>
      <Button
        variant="ghost"
        size="sm"
        px={1}
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-controls={panelId}
        leftIcon={open ? <ChevronDownIcon /> : <ChevronRightIcon />}
        data-testid="supporting-facts-toggle"
      >
        {open ? 'Hide evidence' : `Show evidence (${facts.length})`}
      </Button>

      <Box id={panelId} hidden={!open} mt={1} data-testid="supporting-facts">
        <List
          spacing={0}
          aria-label={`Evidence behind the ${symbol} call`}
          borderTopWidth="1px"
          borderColor="border.subtle"
        >
          {facts.map((fact) => (
            <ListItem
              key={fact.metric}
              py={2.5}
              borderBottomWidth="1px"
              borderColor="border.subtle"
              data-testid="supporting-fact"
              data-metric={fact.metric}
            >
              <Flex align="baseline" justify="space-between" gap={3}>
                <Text fontSize="sm" fontWeight={600} minW={0}>
                  {fact.label}
                </Text>
                <Text
                  className="tabular"
                  fontSize="sm"
                  fontWeight={600}
                  whiteSpace="nowrap"
                  flexShrink={0}
                >
                  <Text as="span" data-testid="fact-value">
                    {fact.value}
                  </Text>
                  {fact.unit && (
                    <Text as="span" fontSize="xs" fontWeight={400} color="fg.muted">
                      {' '}
                      {fact.unit}
                    </Text>
                  )}
                </Text>
              </Flex>

              <Text fontSize="xs" color="fg.subtle" mt={0.5}>
                {fact.metric}
              </Text>

              <Text fontSize="sm" color="fg.muted" mt={1}>
                {fact.interpretation}
              </Text>

              {!fact.verified && (
                // The value above is the measured one; this flags that the
                // model quoted a different figure for it.
                <Text fontSize="xs" color="warning.fg" mt={1} data-testid="fact-corrected">
                  Corrected: the model quoted a value this figure does not have.
                </Text>
              )}
            </ListItem>
          ))}
        </List>
      </Box>
    </Box>
  )
}

export default SupportingFacts
