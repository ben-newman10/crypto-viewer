/**
 * Shared presentation for empty, error and offline states.
 *
 * Every async view in the app funnels its non-happy paths through this
 * component so that messaging, spacing and affordances stay consistent.
 */

import { InfoOutlineIcon, WarningTwoIcon } from '@chakra-ui/icons'
import { Box, Button, Center, Heading, Icon, Text, VStack } from '@chakra-ui/react'
import type { ReactNode } from 'react'

export type StateTone = 'error' | 'empty' | 'warning'

const TONES = {
  error: { fg: 'loss.fg', bg: 'loss.subtle', icon: WarningTwoIcon },
  warning: { fg: 'warning.fg', bg: 'warning.subtle', icon: WarningTwoIcon },
  empty: { fg: 'fg.muted', bg: 'bg.subtle', icon: InfoOutlineIcon },
} as const

export interface StatePanelProps {
  tone?: StateTone
  title: string
  description?: ReactNode
  /** Label for the primary action; omit to render no button. */
  actionLabel?: string
  onAction?: () => void
  isActionLoading?: boolean
  /** Marks the panel as an assertive live region for failures. */
  isAlert?: boolean
  'data-testid'?: string
}

export function StatePanel({
  tone = 'empty',
  title,
  description,
  actionLabel,
  onAction,
  isActionLoading,
  isAlert = tone === 'error',
  'data-testid': testId,
}: StatePanelProps) {
  const { fg, bg, icon } = TONES[tone]

  return (
    <Center
      // `role="alert"` announces failures immediately; informational empty
      // states are announced politely via role="status".
      role={isAlert ? 'alert' : 'status'}
      py={{ base: 8, md: 10 }}
      px={6}
      borderRadius="lg"
      borderWidth="1px"
      borderStyle="dashed"
      borderColor="border.default"
      bg="bg.surface"
      data-testid={testId}
    >
      <VStack spacing={3} maxW="26rem" textAlign="center">
        <Box
          bg={bg}
          color={fg}
          borderRadius="full"
          w="2.75rem"
          h="2.75rem"
          display="grid"
          placeItems="center"
        >
          <Icon as={icon} boxSize={5} aria-hidden="true" />
        </Box>
        <Heading as="p" size="sm" color="fg.default">
          {title}
        </Heading>
        {description && (
          <Text fontSize="sm" color="fg.muted">
            {description}
          </Text>
        )}
        {actionLabel && onAction && (
          <Button
            variant="outline"
            size="sm"
            onClick={onAction}
            isLoading={isActionLoading}
            mt={1}
          >
            {actionLabel}
          </Button>
        )}
      </VStack>
    </Center>
  )
}

export default StatePanel
