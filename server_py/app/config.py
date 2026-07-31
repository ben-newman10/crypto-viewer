"""
Application configuration helpers.

Centralises the handful of environment-driven switches the backend needs so
that both the app factory and the tests read the same source of truth.
"""

import os
from pathlib import Path

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

# Supplementary market data (CoinGecko market cap / supply, alternative.me
# Fear & Greed) is keyless and free, but it is still an outbound call. This
# switch turns it off for deployments that must not talk to those hosts; the
# affected fields then report as explicitly unavailable, which lowers the
# confidence ceiling rather than silently shrinking the evidence base.
EXTERNAL_MARKET_DATA_ENV_VAR = "CRYPTO_VIEWER_EXTERNAL_MARKET_DATA"

# Where the recommendation audit log is appended. Defaults to `logs/` beside
# the backend package, which is gitignored.
RECOMMENDATION_LOG_ENV_VAR = "CRYPTO_VIEWER_RECOMMENDATION_LOG"

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}

# Injected into every recommendation payload server-side, after the model has
# answered. It is a constant rather than something the model is asked to
# produce, so it cannot be dropped, softened or reworded by a generation.
DISCLAIMER = (
    "Informational only — not financial advice. These are model-generated "
    "observations about market data the app fetched, not a recommendation to buy "
    "or sell any asset. Crypto assets are volatile and you can lose money. Do "
    "your own research."
)


def is_test_mode() -> bool:
    """Return True when the backend should use fake third-party clients."""
    return os.getenv(TEST_MODE_ENV_VAR, "").strip().lower() in _TRUTHY


def external_market_data_enabled() -> bool:
    """Return True when CoinGecko / Fear & Greed lookups are permitted."""
    return os.getenv(EXTERNAL_MARKET_DATA_ENV_VAR, "").strip().lower() not in _FALSY


def recommendation_log_path() -> Path:
    """Path of the append-only recommendation log."""
    configured = os.getenv(RECOMMENDATION_LOG_ENV_VAR, "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "logs" / "recommendations.jsonl"
