/**
 * The single card container used for every panel in the app.
 *
 * Owning the header layout here keeps title sizes, spacing and action
 * placement identical across the dashboard and coin detail views.
 */

import { Box, Flex, Heading, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'

export interface SectionCardProps {
  /** Heading text. Rendered with the element given by `headingAs`. */
  title: string
  /** Heading level — set explicitly so document outline stays ordered. */
  headingAs?: 'h1' | 'h2' | 'h3'
  headingId?: string
  subtitle?: ReactNode
  /** Buttons or controls aligned to the header's trailing edge. */
  actions?: ReactNode
  children: ReactNode
  /** Removes body padding for edge-to-edge content such as tables. */
  flushBody?: boolean
  'aria-describedby'?: string
}

export function SectionCard({
  title,
  headingAs = 'h2',
  headingId,
  subtitle,
  actions,
  children,
  flushBody = false,
}: SectionCardProps) {
  return (
    <Box
      as="section"
      aria-labelledby={headingId}
      bg="bg.surface"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="lg"
      boxShadow="card"
      _dark={{ boxShadow: 'cardDark' }}
      overflow="hidden"
    >
      <Flex
        align={{ base: 'flex-start', sm: 'center' }}
        justify="space-between"
        gap={3}
        direction={{ base: 'column', sm: 'row' }}
        px={{ base: 4, md: 6 }}
        pt={{ base: 4, md: 5 }}
        pb={subtitle ? 3 : 4}
      >
        <Box minW={0}>
          <Heading as={headingAs} id={headingId} size="sm">
            {title}
          </Heading>
          {subtitle && (
            <Text mt={1} fontSize="sm" color="fg.muted">
              {subtitle}
            </Text>
          )}
        </Box>
        {actions && (
          <Flex gap={2} align="center" flexShrink={0}>
            {actions}
          </Flex>
        )}
      </Flex>

      <Box
        px={flushBody ? 0 : { base: 4, md: 6 }}
        pb={flushBody ? 0 : { base: 4, md: 6 }}
        borderTopWidth={flushBody ? '1px' : 0}
        borderColor="border.subtle"
      >
        {children}
      </Box>
    </Box>
  )
}

export default SectionCard
