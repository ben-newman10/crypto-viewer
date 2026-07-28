/**
 * Light/dark mode switch.
 *
 * Icon-only, so it carries an `aria-label` that names the action it performs
 * and a tooltip for sighted users.
 */

import { MoonIcon, SunIcon } from '@chakra-ui/icons'
import { IconButton, Tooltip, useColorMode } from '@chakra-ui/react'

export function ColorModeToggle() {
  const { colorMode, toggleColorMode } = useColorMode()
  const nextMode = colorMode === 'light' ? 'dark' : 'light'
  const label = `Switch to ${nextMode} theme`

  return (
    <Tooltip label={label} openDelay={400}>
      <IconButton
        aria-label={label}
        variant="ghost"
        size="sm"
        onClick={toggleColorMode}
        icon={colorMode === 'light' ? <MoonIcon /> : <SunIcon />}
        data-testid="color-mode-toggle"
      />
    </Tooltip>
  )
}

export default ColorModeToggle
