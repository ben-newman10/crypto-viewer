"""
Scenario flags that steer the fake Coinbase/OpenAI clients during E2E tests.

A test selects one or more flags by setting the ``cv_test_scenario`` cookie to a
comma-separated list (e.g. ``slow-ai,error-prices``). Because the flags travel
on the request, scenarios are scoped to a single browser context and parallel
tests never interfere with one another.
"""

from typing import FrozenSet, Optional

# Delay applied by any "slow-*" flag. Long enough for a test to observe and
# screenshot a loading state, short enough to keep the suite quick.
SLOW_DELAY_SECONDS = 1.2

# --- Supported flags --------------------------------------------------------
EMPTY_PORTFOLIO = "empty-portfolio"

ERROR_PORTFOLIO = "error-portfolio"
ERROR_PRICES = "error-prices"
ERROR_HISTORICAL = "error-historical"
ERROR_AI = "error-ai"
DEGRADED_AI = "degraded-ai"

SLOW_PORTFOLIO = "slow-portfolio"
SLOW_PRICES = "slow-prices"
SLOW_HISTORICAL = "slow-historical"
SLOW_AI = "slow-ai"

# Convenience aggregate flags.
SLOW_ALL = "slow"
ERROR_ALL = "error"

KNOWN_FLAGS: FrozenSet[str] = frozenset(
    {
        EMPTY_PORTFOLIO,
        ERROR_PORTFOLIO,
        ERROR_PRICES,
        ERROR_HISTORICAL,
        ERROR_AI,
        DEGRADED_AI,
        SLOW_PORTFOLIO,
        SLOW_PRICES,
        SLOW_HISTORICAL,
        SLOW_AI,
        SLOW_ALL,
        ERROR_ALL,
    }
)

_SLOW_EXPANSION = {SLOW_PORTFOLIO, SLOW_PRICES, SLOW_HISTORICAL, SLOW_AI}
_ERROR_EXPANSION = {ERROR_PORTFOLIO, ERROR_PRICES, ERROR_HISTORICAL, ERROR_AI}


class Scenario:
    """An immutable set of scenario flags parsed from a request."""

    __slots__ = ("flags",)

    def __init__(self, flags: FrozenSet[str]) -> None:
        self.flags = flags

    @classmethod
    def parse(cls, raw: Optional[str]) -> "Scenario":
        """Parse a comma-separated flag list, expanding the aggregate flags."""
        if not raw:
            return cls(frozenset())

        flags = {part.strip().lower() for part in raw.split(",") if part.strip()}

        if SLOW_ALL in flags:
            flags |= _SLOW_EXPANSION
        if ERROR_ALL in flags:
            flags |= _ERROR_EXPANSION

        return cls(frozenset(flags & KNOWN_FLAGS))

    def has(self, flag: str) -> bool:
        return flag in self.flags

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Scenario({sorted(self.flags)})"
