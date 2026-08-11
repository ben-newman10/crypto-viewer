"""
Tests for the environment-driven switches.

These read like trivia until one of them is wrong in a deployment: a typo in a
numeric setting should not stop the backend booting, and a feature that changes
what the app talks about should not switch itself on.
"""

import pytest

from app import config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        config.CANDIDATE_DISCOVERY_ENV_VAR,
        config.CANDIDATE_LIMIT_ENV_VAR,
        config.UNIVERSE_SIZE_ENV_VAR,
    ):
        monkeypatch.delenv(name, raising=False)


# --- candidate discovery ----------------------------------------------------


def test_candidate_discovery_is_off_unless_asked_for():
    """
    Opt-in, unlike external market data. Market context enriches holdings the
    user already has; discovery changes which assets the app talks about at all,
    so an unset variable must not enable it.
    """
    assert config.candidate_discovery_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " on "])
def test_candidate_discovery_accepts_the_usual_truthy_spellings(monkeypatch, value):
    monkeypatch.setenv(config.CANDIDATE_DISCOVERY_ENV_VAR, value)
    assert config.candidate_discovery_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "maybe"])
def test_anything_else_leaves_discovery_off(monkeypatch, value):
    monkeypatch.setenv(config.CANDIDATE_DISCOVERY_ENV_VAR, value)
    assert config.candidate_discovery_enabled() is False


# --- numeric settings -------------------------------------------------------


def test_the_numeric_settings_have_defaults():
    assert config.candidate_limit() == config.DEFAULT_CANDIDATE_LIMIT
    assert config.universe_size() == config.DEFAULT_UNIVERSE_SIZE


def test_a_numeric_setting_can_be_overridden(monkeypatch):
    monkeypatch.setenv(config.CANDIDATE_LIMIT_ENV_VAR, "3")
    monkeypatch.setenv(config.UNIVERSE_SIZE_ENV_VAR, "100")

    assert config.candidate_limit() == 3
    assert config.universe_size() == 100


@pytest.mark.parametrize("value", ["", "   ", "lots", "3.5", "-1", "0"])
def test_a_malformed_numeric_setting_falls_back_rather_than_failing(monkeypatch, value):
    """
    A bad value in the environment configures an *optional* feature. Refusing to
    boot over it would turn a cosmetic mistake into an outage.
    """
    monkeypatch.setenv(config.CANDIDATE_LIMIT_ENV_VAR, value)
    assert config.candidate_limit() == config.DEFAULT_CANDIDATE_LIMIT


def test_the_universe_covers_everything_the_exchange_could_list():
    """
    A coin missing from the ranked page cannot be ranked, and so can never be a
    candidate. Measured against the live APIs, every one of Coinbase's tradeable
    GBP pairs sat inside the top 250 -- the default has to keep that true with
    room to spare.
    """
    assert config.DEFAULT_UNIVERSE_SIZE >= 250
    assert config.DEFAULT_CANDIDATE_LIMIT < config.DEFAULT_UNIVERSE_SIZE
