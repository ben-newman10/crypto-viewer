/**
 * Ports and URLs shared by the Playwright config and the tests.
 *
 * Deliberately different from the dev defaults (5173 / 3001) so the E2E suite
 * can run while a development server is up.
 */

export const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 3101)
export const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 4173)

export const BASE_URL = `http://127.0.0.1:${FRONTEND_PORT}`
export const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`
