/**
 * Concrete colour values for canvas-rendered charts.
 *
 * Chart.js paints to a canvas and cannot resolve CSS custom properties, so the
 * chart reads literal hex values from the design tokens and picks the light or
 * dark set from the active colour mode. This keeps the chart on-palette without
 * duplicating colour definitions.
 */

import { useColorMode } from '@chakra-ui/react'

import { gain, ink, loss } from './tokens'

export interface ChartPalette {
  gain: string
  loss: string
  neutral: string
  grid: string
  axis: string
  surface: string
  tooltipBg: string
  tooltipFg: string
}

const LIGHT: ChartPalette = {
  gain: gain[700],
  loss: loss[700],
  neutral: ink[500],
  grid: ink[150],
  axis: ink[600],
  surface: '#FFFFFF',
  tooltipBg: ink[900],
  tooltipFg: '#FFFFFF',
}

const DARK: ChartPalette = {
  gain: gain[400],
  loss: loss[400],
  neutral: ink[300],
  grid: '#2A3242',
  axis: '#C3CAD6',
  surface: ink[850],
  tooltipBg: '#F2F4F8',
  tooltipFg: ink[900],
}

export function useChartPalette(): ChartPalette {
  const { colorMode } = useColorMode()
  return colorMode === 'dark' ? DARK : LIGHT
}
