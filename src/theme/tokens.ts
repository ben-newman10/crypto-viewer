/**
 * Design tokens for Crypto Viewer.
 *
 * Every colour used in the UI comes from this file, and every contrast pairing
 * documented below has been checked against WCAG 2.1 AA (4.5:1 for body text,
 * 3:1 for large text and non-text UI affordances such as focus rings and form
 * control borders).
 */

/** Primary brand ramp — indigo/violet. */
export const brand = {
  50: '#F1F0FE',
  100: '#E4E2FC',
  200: '#CAC6F8',
  300: '#AAA4F2',
  400: '#8B84FF',
  500: '#6259E0',
  600: '#4F46C7',
  700: '#423AA8',
  800: '#332C85',
  900: '#242066',
} as const

/** Positive / gain ramp — green. */
export const gain = {
  50: '#E6F6EE',
  100: '#C7EBDA',
  200: '#8FD8B6',
  300: '#5FC796',
  400: '#3ED598',
  500: '#12945C',
  600: '#0F8452',
  700: '#0B7A4B',
  800: '#0A6340',
  900: '#074A30',
} as const

/** Negative / loss ramp — red. */
export const loss = {
  50: '#FDECEA',
  100: '#FBD5D1',
  200: '#F6ABA3',
  300: '#F08277',
  400: '#FF8B80',
  500: '#DC2E22',
  600: '#CE2A1F',
  700: '#C0271C',
  800: '#9B1F16',
  900: '#71160F',
} as const

/** Caution ramp — amber. */
export const warning = {
  50: '#FFF6E5',
  100: '#FDE8C0',
  200: '#F7CE84',
  300: '#EFB44C',
  400: '#FFC24D',
  500: '#C57C00',
  600: '#A66300',
  700: '#8A5300',
  800: '#6E4200',
  900: '#4F2F00',
} as const

/** Neutral ramp used for text, surfaces and borders. */
export const ink = {
  25: '#FBFCFD',
  50: '#F7F8FA',
  100: '#EDF0F4',
  150: '#E3E7ED',
  200: '#D5DAE3',
  300: '#B6BEC9',
  400: '#767E8C',
  500: '#5A6478',
  600: '#4A5568',
  700: '#3A4354',
  800: '#232A38',
  850: '#1A1F2A',
  900: '#12151C',
  950: '#0B0D12',
} as const

/**
 * Dark-mode tinted surfaces. Deliberately desaturated so that the light
 * foreground ramps stay above 4.5:1 when laid on top of them.
 */
export const darkTint = {
  gain: '#12291F',
  loss: '#2C1917',
  warning: '#2C2312',
  brand: '#1E1B33',
  neutral: '#20263300',
} as const

/**
 * Type scale. A restrained 7-step ramp; nothing in the UI uses an off-scale
 * font size.
 */
export const fontSizes = {
  xs: '0.75rem', // 12px — table meta, badges
  sm: '0.875rem', // 14px — secondary text
  md: '1rem', // 16px — body
  lg: '1.125rem', // 18px — card titles
  xl: '1.375rem', // 22px — section headings
  '2xl': '1.75rem', // 28px — page heading
  '3xl': '2.25rem', // 36px — hero figure
  '4xl': '2.75rem', // 44px — hero figure (desktop)
} as const

/** Border radius tokens. */
export const radii = {
  none: '0',
  sm: '6px',
  md: '10px',
  lg: '14px',
  xl: '20px',
  full: '9999px',
} as const

/**
 * Elevation tokens. Light mode leans on soft shadows; dark mode leans on
 * borders (shadows are near-invisible on dark surfaces) with a faint glow.
 */
export const shadows = {
  xs: '0 1px 2px rgba(16, 21, 31, 0.06)',
  card: '0 1px 2px rgba(16, 21, 31, 0.05), 0 4px 12px -2px rgba(16, 21, 31, 0.07)',
  cardHover: '0 2px 4px rgba(16, 21, 31, 0.06), 0 12px 24px -4px rgba(16, 21, 31, 0.12)',
  cardDark: '0 1px 2px rgba(0, 0, 0, 0.45)',
  cardHoverDark: '0 8px 24px -6px rgba(0, 0, 0, 0.6)',
  popover: '0 12px 32px -8px rgba(16, 21, 31, 0.24)',
} as const

/** Motion tokens. Kept short — micro-interactions, not animations. */
export const transitions = {
  fast: '120ms cubic-bezier(0.2, 0, 0.2, 1)',
  base: '180ms cubic-bezier(0.2, 0, 0.2, 1)',
} as const
