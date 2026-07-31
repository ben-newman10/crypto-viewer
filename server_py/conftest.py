"""
Shared pytest configuration for the backend test suite.

Test mode is enabled before the application package is imported so that every
test runs against the fake Coinbase/OpenAI clients. This keeps the suite
hermetic: no credentials are required and no third-party request is ever made.
"""

import os

import pytest

from app.config import TEST_MODE_ENV_VAR

os.environ[TEST_MODE_ENV_VAR] = "1"


@pytest.fixture(autouse=True)
def _test_mode_enabled(monkeypatch):
    """Guarantee test mode stays on even if a test mutates the environment."""
    monkeypatch.setenv(TEST_MODE_ENV_VAR, "1")
