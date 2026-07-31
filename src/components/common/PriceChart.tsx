/**
 * 24-hour price line chart.
 *
 * Canvas content is invisible to assistive technology, so the chart ships with
 * three accessibility affordances:
 *  - the canvas is hidden from AT and wrapped in a labelled `role="img"`,
 *  - the label summarises the trend in words,
 *  - a keyboard-reachable disclosure exposes the same data as a real table.
 */

import { ChevronDownIcon, ChevronRightIcon } from '@chakra-ui/icons'
import {
  Box,
  Button,
  Table,
  TableContainer,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from '@chakra-ui/react'
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartOptions,
  type ScriptableContext,
} from 'chart.js'
import { useId, useMemo, useState } from 'react'
import { Line } from 'react-chartjs-2'

import { useReducedMotion } from '../../hooks/useReducedMotion'
import type { Candle } from '../../lib/api'
import {
  directionOf,
  formatAxisCurrency,
  formatCurrency,
  formatHourLabel,
  formatPercent,
  toNumber,
} from '../../lib/format'
import { useChartPalette } from '../../theme/chartPalette'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip)

export interface PriceChartProps {
  currency: string
  /** Candles ordered oldest-first. */
  series: Candle[]
  /** 24h percentage change, used to colour the line. */
  change24h: number | null
}

export function PriceChart({ currency, series, change24h }: PriceChartProps) {
  const [showTable, setShowTable] = useState(false)
  const tableId = useId()
  const reducedMotion = useReducedMotion()
  const palette = useChartPalette()

  const direction = directionOf(change24h)
  const lineColor =
    direction === 'up'
      ? palette.gain
      : direction === 'down'
        ? palette.loss
        : palette.neutral

  const points = useMemo(
    () =>
      series
        .map((candle) => ({ time: candle.time, close: toNumber(candle.close) }))
        .filter((point): point is { time: string; close: number } => point.close != null),
    [series],
  )

  const summary = useMemo(() => {
    if (points.length === 0) return `No price history available for ${currency}.`
    const first = points[0].close
    const last = points[points.length - 1].close
    const low = Math.min(...points.map((point) => point.close))
    const high = Math.max(...points.map((point) => point.close))
    const word = direction === 'up' ? 'up' : direction === 'down' ? 'down' : 'flat'
    return (
      `Line chart of ${currency} price over the last 24 hours: ` +
      `from ${formatCurrency(first)} to ${formatCurrency(last)}, ${word} ` +
      `${formatPercent(change24h)}. Low ${formatCurrency(low)}, high ${formatCurrency(high)}.`
    )
  }, [points, currency, direction, change24h])

  const data = useMemo(
    () => ({
      labels: points.map((point) => formatHourLabel(point.time)),
      datasets: [
        {
          label: `${currency} price`,
          data: points.map((point) => point.close),
          borderColor: lineColor,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: lineColor,
          pointHoverBorderColor: palette.surface,
          pointHoverBorderWidth: 2,
          tension: 0.35,
          fill: true,
          backgroundColor: (context: ScriptableContext<'line'>) => {
            const { ctx, chartArea } = context.chart
            if (!chartArea) return 'transparent'
            const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom)
            gradient.addColorStop(0, `${lineColor}2E`)
            gradient.addColorStop(1, `${lineColor}00`)
            return gradient
          },
        },
      ],
    }),
    [points, currency, lineColor, palette.surface],
  )

  const options = useMemo<ChartOptions<'line'>>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      // Honour prefers-reduced-motion for the JS-driven draw animation.
      animation: reducedMotion ? false : { duration: 400 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: palette.tooltipBg,
          titleColor: palette.tooltipFg,
          bodyColor: palette.tooltipFg,
          padding: 10,
          displayColors: false,
          callbacks: {
            label: (context) => formatCurrency(context.parsed.y),
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          border: { color: palette.grid },
          ticks: {
            color: palette.axis,
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 6,
            font: { size: 11 },
          },
        },
        y: {
          grid: { color: palette.grid },
          border: { display: false },
          ticks: {
            color: palette.axis,
            maxTicksLimit: 5,
            font: { size: 11 },
            callback: (value) => formatAxisCurrency(Number(value)),
          },
        },
      },
    }),
    [reducedMotion, palette],
  )

  if (points.length === 0) return null

  return (
    <Box>
      <Box
        role="img"
        aria-label={summary}
        h={{ base: '13rem', md: '17rem' }}
        w="100%"
        data-testid="price-chart"
      >
        {/* The canvas carries no accessible information of its own. */}
        <Line data={data} options={options} aria-hidden="true" />
      </Box>

      <Button
        variant="ghost"
        size="sm"
        mt={3}
        onClick={() => setShowTable((open) => !open)}
        aria-expanded={showTable}
        aria-controls={tableId}
        leftIcon={showTable ? <ChevronDownIcon /> : <ChevronRightIcon />}
      >
        {showTable ? 'Hide price data table' : 'View price data as a table'}
      </Button>

      <Box id={tableId} hidden={!showTable} mt={2}>
        {/*
          The container scrolls, so it must be focusable and named — otherwise
          keyboard-only users cannot reach the rows below the fold.
        */}
        <TableContainer
          maxH="18rem"
          overflowY="auto"
          tabIndex={0}
          role="group"
          aria-label={`${currency} price history, scrollable`}
        >
          <Table
            size="sm"
            variant="simple"
            aria-label={`Hourly ${currency} closing prices over the last 24 hours`}
          >
            <Thead position="sticky" top={0} bg="bg.surface" zIndex={1}>
              <Tr>
                <Th scope="col">Time (UTC)</Th>
                <Th scope="col" isNumeric>
                  Close
                </Th>
                <Th scope="col" isNumeric>
                  Low
                </Th>
                <Th scope="col" isNumeric>
                  High
                </Th>
              </Tr>
            </Thead>
            <Tbody>
              {series.map((candle) => (
                <Tr key={candle.time}>
                  <Th
                    scope="row"
                    fontWeight={500}
                    textTransform="none"
                    letterSpacing="normal"
                    color="fg.default"
                  >
                    {formatHourLabel(candle.time)}
                  </Th>
                  <Td isNumeric className="tabular">
                    {formatCurrency(toNumber(candle.close))}
                  </Td>
                  <Td isNumeric className="tabular">
                    {formatCurrency(toNumber(candle.low))}
                  </Td>
                  <Td isNumeric className="tabular">
                    {formatCurrency(toNumber(candle.high))}
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableContainer>
      </Box>
    </Box>
  )
}

export default PriceChart
