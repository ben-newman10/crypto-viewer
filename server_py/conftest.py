"""
Shared pytest configuration for the backend test suite.

Test mode is enabled before the application package is imported so that every
test runs against the fake Coinbase/OpenAI clients. This keeps the suite
hermetic: no credentials are required and no third-party request is ever made.
"""

import os
import tempfile

import pytest

from app.config import RECOMMENDATION_LOG_ENV_VAR, TEST_MODE_ENV_VAR

os.environ[TEST_MODE_ENV_VAR] = "1"

# The recommendation pipeline appends an audit entry per run. Point it at a
# throwaway file so a test run never accumulates entries in the repository.
_LOG_DIR = tempfile.mkdtemp(prefix="crypto-viewer-test-logs-")
os.environ[RECOMMENDATION_LOG_ENV_VAR] = os.path.join(_LOG_DIR, "recommendations.jsonl")


@pytest.fixture(autouse=True)
def _test_mode_enabled(monkeypatch):
    """Guarantee test mode stays on even if a test mutates the environment."""
    monkeypatch.setenv(TEST_MODE_ENV_VAR, "1")


@pytest.fixture
def recommendation_log_file(tmp_path, monkeypatch):
    """Redirect the recommendation log to a per-test file and hand back its path."""
    path = tmp_path / "recommendations.jsonl"
    monkeypatch.setenv(RECOMMENDATION_LOG_ENV_VAR, str(path))
    return path
