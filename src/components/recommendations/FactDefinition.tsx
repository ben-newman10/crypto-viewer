/**
 * "What is this?" — the plain-English definition of one metric, on demand.
 *
 * A reader who does not know what RSI is cannot judge a call built on it, and
 * the model's own sentence about today's value does not fill that gap. The
 * definition comes from the backend's metric catalogue rather than the model,
 * so it is the same every run and cannot be got wrong.
 *
 * Collapsed by default: someone who already knows the terms would find a
 * paragraph under every figure to be noise, and the evidence list is long
 * enough already. Deliberately renders no heading — the panel it sits in has a
 * fixed heading outline (h2 for the panel, h3 per card) that the accessibility
 * tests assert on.
 */

import { ChevronDownIcon, ChevronRightIcon } from '@chakra-ui/icons'
import { Box, Button, Text } from '@chakra-ui/react'
import { useId, useState } from 'react'

export interface FactDefinitionProps {
  /** Plain-English definition. Nothing renders when this is empty. */
  plain: string
  /** Metric name, used to tell one row's toggle from another's. */
  label: string
}

export function FactDefinition({ plain, label }: FactDefinitionProps) {
  const [open, setOpen] = useState(false)
  const panelId = useId()

  if (!plain) {
    return null
  }

  return (
    <Box mt={1}>
      <Button
        variant="ghost"
        size="xs"
        px={1}
        fontWeight={500}
        color="fg.muted"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-controls={panelId}
        // The visible label repeats on every row, so the accessible name
        // carries the metric it belongs to.
        aria-label={open ? `Hide explanation of ${label}` : `What is ${label}?`}
        leftIcon={open ? <ChevronDownIcon /> : <ChevronRightIcon />}
        data-testid="fact-definition-toggle"
      >
        {open ? 'Hide explanation' : 'What is this?'}
      </Button>

      <Box
        id={panelId}
        hidden={!open}
        mt={1}
        ml={1}
        pl={2.5}
        borderLeftWidth="2px"
        borderColor="border.subtle"
        data-testid="fact-definition"
      >
        <Text fontSize="xs" color="fg.muted">
          {plain}
        </Text>
      </Box>
    </Box>
  )
}

export default FactDefinition
