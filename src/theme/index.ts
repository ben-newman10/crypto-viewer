/**
 * Chakra theme for Crypto Viewer.
 *
 * Wires the design tokens into Chakra's theme so that components pick up the
 * palette, radii, shadows and focus treatment automatically. Semantic tokens
 * (`bg.surface`, `fg.muted`, `gain.fg`, ...) are the only colours components
 * should reference — that keeps light and dark mode in sync from one place.
 */

import { extendTheme, type ThemeConfig } from '@chakra-ui/react'
import {
  brand,
  darkTint,
  fontSizes,
  gain,
  ink,
  loss,
  radii,
  shadows,
  transitions,
  warning,
} from './tokens'

const config: ThemeConfig = {
  // Pinned rather than following the OS so that screenshots and the E2E suite
  // start from a known state; users toggle explicitly from the header.
  initialColorMode: 'light',
  useSystemColorMode: false,
}

const theme = extendTheme({
  config,

  colors: { brand, gain, loss, warning, ink },

  fonts: {
    heading:
      '"Inter var", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif',
    body:
      '"Inter var", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif',
    // Numeric columns use the same family but with tabular figures applied via
    // `fontVariantNumeric`, so digits line up without a font swap.
    mono: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
  },

  fontSizes,
  radii,
  shadows,

  semanticTokens: {
    colors: {
      // Surfaces
      'bg.canvas': { default: ink[50], _dark: ink[900] },
      'bg.surface': { default: '#FFFFFF', _dark: ink[850] },
      'bg.subtle': { default: ink[100], _dark: ink[800] },
      'bg.hover': { default: ink[50], _dark: ink[800] },
      'bg.inverse': { default: ink[900], _dark: ink[25] },

      // Foreground
      'fg.default': { default: ink[900], _dark: '#F2F4F8' },
      'fg.muted': { default: ink[600], _dark: '#C3CAD6' },
      'fg.subtle': { default: ink[500], _dark: '#A5AEBD' },
      'fg.inverse': { default: '#FFFFFF', _dark: ink[900] },

      // Borders: `border.subtle` is decorative, `border.control` is used for
      // form controls and meets the 3:1 non-text contrast requirement.
      'border.subtle': { default: ink[150], _dark: '#2A3242' },
      'border.default': { default: ink[200], _dark: '#333C4E' },
      'border.control': { default: ink[400], _dark: '#737D90' },

      // Accent
      'accent.fg': { default: brand[700], _dark: brand[300] },
      'accent.solid': { default: brand[600], _dark: brand[500] },
      'accent.solidHover': { default: brand[700], _dark: brand[600] },
      'accent.subtle': { default: brand[50], _dark: darkTint.brand },
      'accent.ring': { default: brand[600], _dark: brand[400] },

      // Gain / loss / warning: `*.fg` on `bg.surface` and on `*.subtle` both
      // clear 4.5:1.
      'gain.fg': { default: gain[700], _dark: gain[400] },
      'gain.subtle': { default: gain[50], _dark: darkTint.gain },
      'gain.solid': { default: gain[700], _dark: gain[500] },
      'loss.fg': { default: loss[700], _dark: loss[400] },
      'loss.subtle': { default: loss[50], _dark: darkTint.loss },
      'loss.solid': { default: loss[700], _dark: loss[500] },
      'warning.fg': { default: warning[700], _dark: warning[400] },
      'warning.subtle': { default: warning[50], _dark: darkTint.warning },

      // Neutral (flat / zero change)
      'neutral.fg': { default: ink[600], _dark: '#C3CAD6' },
      'neutral.subtle': { default: ink[100], _dark: ink[800] },
    },
  },

  styles: {
    global: {
      'html, body': {
        bg: 'bg.canvas',
        color: 'fg.default',
        fontSize: 'md',
        lineHeight: 1.55,
        WebkitFontSmoothing: 'antialiased',
      },
      '*::selection': {
        bg: 'accent.subtle',
        color: 'accent.fg',
      },
      // A single, unmistakable focus treatment for every focusable element.
      // `:focus-visible` keeps it off for mouse clicks but always on for
      // keyboard navigation.
      '*:focus:not(:focus-visible)': {
        boxShadow: 'none',
        outline: 'none',
      },
      '*:focus-visible': {
        outline: '2px solid',
        outlineColor: 'accent.ring',
        outlineOffset: '2px',
        borderRadius: 'sm',
      },
      // Numeric cells share one figure treatment so columns align.
      '.tabular': {
        fontVariantNumeric: 'tabular-nums',
        fontFeatureSettings: '"tnum"',
      },
    },
  },

  components: {
    Heading: {
      baseStyle: {
        color: 'fg.default',
        fontWeight: 650,
        letterSpacing: '-0.011em',
      },
      sizes: {
        xs: { fontSize: 'sm', lineHeight: 1.4 },
        sm: { fontSize: 'lg', lineHeight: 1.35 },
        md: { fontSize: 'xl', lineHeight: 1.3 },
        lg: { fontSize: '2xl', lineHeight: 1.25 },
      },
      defaultProps: { size: 'md' },
    },

    Text: {
      baseStyle: { color: 'fg.default' },
    },

    Link: {
      baseStyle: {
        color: 'accent.fg',
        fontWeight: 500,
        textUnderlineOffset: '3px',
        transition: `color ${transitions.fast}`,
        _hover: { color: 'accent.solidHover', textDecoration: 'underline' },
      },
    },

    Card: {
      baseStyle: {
        container: {
          bg: 'bg.surface',
          borderRadius: 'lg',
          borderWidth: '1px',
          borderColor: 'border.subtle',
          boxShadow: shadows.card,
          _dark: { boxShadow: shadows.cardDark },
        },
      },
    },

    Button: {
      baseStyle: {
        borderRadius: 'md',
        fontWeight: 600,
        transition: `background-color ${transitions.fast}, color ${transitions.fast}, border-color ${transitions.fast}, transform ${transitions.fast}`,
        _active: { transform: 'translateY(1px)' },
      },
      variants: {
        solid: {
          bg: 'accent.solid',
          color: '#FFFFFF',
          _hover: { bg: 'accent.solidHover', _disabled: { bg: 'accent.solid' } },
          _active: { bg: 'accent.solidHover' },
        },
        outline: {
          borderColor: 'border.control',
          color: 'fg.default',
          _hover: { bg: 'bg.hover' },
        },
        ghost: {
          color: 'fg.muted',
          _hover: { bg: 'bg.subtle', color: 'fg.default' },
        },
      },
      defaultProps: { variant: 'solid', colorScheme: undefined },
    },

    Input: {
      variants: {
        outline: {
          field: {
            bg: 'bg.surface',
            borderColor: 'border.control',
            borderRadius: 'md',
            _hover: { borderColor: 'accent.ring' },
            _focusVisible: {
              borderColor: 'accent.ring',
              boxShadow: 'none',
            },
            _placeholder: { color: 'fg.subtle' },
          },
        },
      },
    },

    FormLabel: {
      baseStyle: {
        color: 'fg.muted',
        fontSize: 'sm',
        fontWeight: 600,
        mb: 1.5,
      },
    },

    Table: {
      baseStyle: {
        th: {
          color: 'fg.muted',
          fontSize: 'xs',
          fontWeight: 600,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          borderColor: 'border.subtle',
        },
        td: {
          borderColor: 'border.subtle',
          color: 'fg.default',
        },
      },
    },

    Skeleton: {
      baseStyle: {
        borderRadius: 'sm',
      },
    },

    Tooltip: {
      baseStyle: {
        bg: 'bg.inverse',
        color: 'fg.inverse',
        borderRadius: 'sm',
        fontSize: 'sm',
        px: 2.5,
        py: 1.5,
      },
    },
  },
})

export default theme
