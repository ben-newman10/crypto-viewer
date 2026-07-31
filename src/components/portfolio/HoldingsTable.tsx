/**
 * Holdings table for tablet and desktop widths.
 *
 * Accessibility notes:
 *  - column headers use `scope="col"`, the asset cell uses `scope="row"`,
 *  - sortable headers carry `aria-sort` and wrap a real `<button>`,
 *  - numeric columns are right-aligned with tabular figures so digits line up.
 */

import { ChevronDownIcon, ChevronUpIcon, WarningTwoIcon } from '@chakra-ui/icons'
import {
  Box,
  HStack,
  Icon,
  Link as ChakraLink,
  Skeleton,
  Table,
  TableContainer,
  Tag,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
  VisuallyHidden,
} from '@chakra-ui/react'
import { Link as RouterLink } from 'react-router-dom'

import type { HoldingView } from '../../hooks/usePortfolio'
import { formatAmount, formatCurrency } from '../../lib/format'
import AssetBadge from '../common/AssetBadge'
import ChangeIndicator from '../common/ChangeIndicator'
import { ariaSortFor, type SortKey, type SortState } from './sorting'

interface Column {
  key: SortKey
  label: string
  numeric: boolean
}

const COLUMNS: Column[] = [
  { key: 'currency', label: 'Asset', numeric: false },
  { key: 'balance', label: 'Balance', numeric: true },
  { key: 'price', label: 'Price', numeric: true },
  { key: 'change24h', label: '24h', numeric: true },
  { key: 'value', label: 'Value', numeric: true },
]

export interface HoldingsTableProps {
  holdings: HoldingView[]
  sort: SortState
  onSort: (key: SortKey) => void
  /** Renders placeholder rows while the first payload is in flight. */
  isLoading?: boolean
  skeletonRows?: number
}

function SortButton({
  column,
  sort,
  onSort,
}: {
  column: Column
  sort: SortState
  onSort: (key: SortKey) => void
}) {
  const isActive = sort.key === column.key
  const ArrowIcon = sort.direction === 'asc' ? ChevronUpIcon : ChevronDownIcon

  return (
    <Box
      as="button"
      type="button"
      onClick={() => onSort(column.key)}
      display="inline-flex"
      alignItems="center"
      gap={1}
      borderRadius="sm"
      color={isActive ? 'fg.default' : 'inherit'}
      transition="color 120ms"
      _hover={{ color: 'fg.default' }}
      justifyContent={column.numeric ? 'flex-end' : 'flex-start'}
      w="100%"
    >
      {column.label}
      {isActive ? (
        <ArrowIcon boxSize={3} aria-hidden="true" />
      ) : (
        <Box as="span" w={3} aria-hidden="true" />
      )}
      <VisuallyHidden>
        {isActive
          ? `, sorted ${sort.direction === 'asc' ? 'ascending' : 'descending'}. Activate to reverse the order.`
          : ', not sorted. Activate to sort by this column.'}
      </VisuallyHidden>
    </Box>
  )
}

function PriceCell({ holding }: { holding: HoldingView }) {
  if (holding.priceState === 'loading') return <Skeleton height="1rem" ml="auto" width="4.5rem" />

  if (holding.priceState === 'error') {
    return (
      <Tooltip label={holding.priceError ?? 'Price unavailable'}>
        <HStack spacing={1.5} justify="flex-end" color="warning.fg">
          <Icon as={WarningTwoIcon} boxSize={3} aria-hidden="true" />
          <Text as="span" fontSize="sm">
            Unavailable
          </Text>
        </HStack>
      </Tooltip>
    )
  }

  return <>{formatCurrency(holding.price)}</>
}

export function HoldingsTable({
  holdings,
  sort,
  onSort,
  isLoading = false,
  skeletonRows = 4,
}: HoldingsTableProps) {
  return (
    <TableContainer>
      <Table variant="simple" size="md" aria-label="Cryptocurrency holdings">
        <Thead>
          <Tr>
            {COLUMNS.map((column) => (
              <Th
                key={column.key}
                scope="col"
                isNumeric={column.numeric}
                aria-sort={ariaSortFor(sort, column.key)}
                px={{ base: 3, md: 4 }}
              >
                <SortButton column={column} sort={sort} onSort={onSort} />
              </Th>
            ))}
          </Tr>
        </Thead>

        <Tbody>
          {isLoading
            ? Array.from({ length: skeletonRows }, (_, index) => (
                <Tr key={`skeleton-${index}`} data-testid="holding-row-skeleton">
                  {COLUMNS.map((column) => (
                    <Td key={column.key} px={{ base: 3, md: 4 }}>
                      <Skeleton
                        height="1.1rem"
                        width={column.key === 'currency' ? '7rem' : '4.5rem'}
                        ml={column.numeric ? 'auto' : 0}
                      />
                    </Td>
                  ))}
                </Tr>
              ))
            : holdings.map((holding) => (
                <Tr
                  key={holding.currency}
                  data-testid="holding-row"
                  data-currency={holding.currency}
                  transition="background-color 120ms"
                  _hover={{ bg: 'bg.hover' }}
                >
                  <Th
                    scope="row"
                    px={{ base: 3, md: 4 }}
                    textTransform="none"
                    letterSpacing="normal"
                    fontSize="md"
                    fontWeight={600}
                    color="fg.default"
                  >
                    <HStack spacing={3}>
                      <AssetBadge currency={holding.currency} />
                      {holding.isCash ? (
                        <HStack spacing={2}>
                          <Text as="span">{holding.currency}</Text>
                          <Tag size="sm" bg="bg.subtle" color="fg.muted" borderRadius="full">
                            Cash
                          </Tag>
                        </HStack>
                      ) : (
                        <ChakraLink
                          as={RouterLink}
                          to={`/coin/${holding.currency}`}
                          fontWeight={600}
                          color="fg.default"
                          _hover={{ color: 'accent.fg' }}
                        >
                          {holding.currency}
                          <VisuallyHidden> — view price detail</VisuallyHidden>
                        </ChakraLink>
                      )}
                    </HStack>
                  </Th>

                  <Td isNumeric className="tabular" px={{ base: 3, md: 4 }}>
                    {formatAmount(holding.balance, holding.currency)}
                  </Td>

                  <Td isNumeric className="tabular" px={{ base: 3, md: 4 }}>
                    <PriceCell holding={holding} />
                  </Td>

                  <Td isNumeric px={{ base: 3, md: 4 }}>
                    {holding.isCash ? (
                      <Text as="span" fontSize="sm" color="fg.subtle">
                        —
                      </Text>
                    ) : (
                      <ChangeIndicator
                        percent={holding.change24h}
                        size="sm"
                        srSuffix={`over the last 24 hours for ${holding.currency}`}
                      />
                    )}
                  </Td>

                  <Td
                    isNumeric
                    className="tabular"
                    px={{ base: 3, md: 4 }}
                    fontWeight={600}
                  >
                    {formatCurrency(holding.value)}
                  </Td>
                </Tr>
              ))}
        </Tbody>
      </Table>
    </TableContainer>
  )
}

export default HoldingsTable
