"""
Application configuration helpers.

Centralises the handful of environment-driven switches the backend needs so
that both the app factory and the tests read the same source of truth.
"""

import os

# Environment variable that swaps the outbound Coinbase/OpenAI clients for
# deterministic in-process fakes. Used by the Playwright E2E suite and by the
# backend's own pytest suite so that no test ever performs a real network call
# to a third-party API.
TEST_MODE_ENV_VAR = "CRYPTO_VIEWER_TEST_MODE"

# Name of the cookie an E2E test sets to steer the fake services into a
# particular scenario (slow responses, upstream failures, empty portfolio...).
# A cookie is used rather than a server-global flag so that scenarios are
# scoped to a single browser context and parallel tests cannot interfere.
SCENARIO_COOKIE = "cv_test_scenario"

_TRUTHY = {"1", "true", "yes", "on"}


def is_test_mode() -> bool:
    """Return True when the backend should use fake third-party clients."""
    return os.getenv(TEST_MODE_ENV_VAR, "").strip().lower() in _TRUTHY
