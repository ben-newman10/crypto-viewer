"""
Choosing which assets the user does not hold are worth looking at.

This module decides what the pipeline *examines*, not what it recommends. That
distinction shapes every decision here:

* **It stratifies rather than scores.** A composite "attractiveness" number
  would be the single most citable-looking figure in the whole context, and the
  model would reach for it -- but it would be an artefact of this file's
  weightings, not a measurement of anything. So candidates are drawn from a few
  named angles instead, and the only thing recorded about the choice is which
  angle it came from.
* **Every rejection is named.** ``screen`` returns the excluded assets and why,
  so the shortlist can be shown as a decision rather than an oracle.
* **It is pure and deterministic.** No I/O, and ties broken on rank, so the same
  universe always yields the same shortlist -- which is what makes it testable
  and what stops the panel reshuffling on every fifteen-minute refetch.

Nothing here talks to the model. The screener's output becomes ordinary
grounding: a rank is a measurement, and the chosen angle is a closed vocabulary
that verifies like any other categorical field.
"""

import logging
import statistics
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from pydantic import BaseModel, Field

try:  # pragma: no cover
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal  # type: ignore

from .market_context_service import UniverseRow

#: Ranked below this and a coin is out, however it looks on other measures.
#: Coinbase's own listing is already a curated set, so this rarely bites -- it
#: is a guard against a future listing far down the tail, not a main filter.
CANDIDATE_RANK_FLOOR = 150

#: Minimum 24-hour traded volume, in the quote currency. A market too thin to
#: enter or leave is not a suggestion worth making.
MIN_TURNOVER = 10_000_000.0

#: Default shortlist size. Each survivor costs a candle request and a card's
#: worth of prompt.
SHORTLIST_SIZE = 5

#: Balances held as cash rather than as a position. Mirrors the context
#: builder's own set.
FIAT_SYMBOLS: FrozenSet[str] = frozenset({"GBP", "USD", "EUR"})

#: Curated, and curated on purpose.
#:
#: The tempting alternative is to detect a stablecoin numerically -- "a coin
#: whose price barely moved is pegged". Measured against a live universe that
#: rule classifies **Bitcoin** as a stablecoin on any quiet week (BTC has posted
#: -0.5% / -0.8% / -0.4% over 24h / 7d / 30d), and tightening the threshold only
#: narrows the window in which it is catastrophically wrong. A stale list fails
#: safely: at worst a newly listed stablecoin gets assessed on its data and
#: reported as going nowhere. A false positive silently deletes a major asset
#: from every run. The upgrade path, if this ever needs to be dynamic, is
#: CoinGecko's ``category=stablecoins`` page -- another lookup, not a heuristic.
STABLECOINS: FrozenSet[str] = frozenset(
    {"USDT", "USDC", "DAI", "PYUSD", "TUSD", "USDP", "GUSD", "FDUSD", "USDS", "RLUSD"}
)

#: Assets that are really a wrapper around, or a staked claim on, something
#: else. Suggesting WBTC to someone who already holds BTC is not a new position,
#: it is the same exposure under another ticker.
WRAPPED_EQUIVALENTS: Dict[str, str] = {
    "WBTC": "BTC",
    "CBBTC": "BTC",
    "TBTC": "BTC",
    "WETH": "ETH",
    "STETH": "ETH",
    "WSTETH": "ETH",
    "CBETH": "ETH",
    "RETH": "ETH",
    "WEETH": "ETH",
    "MSOL": "SOL",
    "JITOSOL": "SOL",
    "CBDOGE": "DOGE",
}

#: Rank at or above which a coin counts as a large cap for stratification.
LARGE_CAP_RANK = 20

#: Quantile of 7-day change above which a coin counts as recently strong.
RECENT_STRENGTH_QUANTILE = 0.75

ScreenReason = Literal["large_cap", "deep_drawdown", "recent_strength", "next_by_rank"]

ExclusionReason = Literal[
    "already_held",
    "fiat",
    "stablecoin",
    "duplicate_exposure",
    "not_tradeable",
    "unranked",
    "below_rank_floor",
    "thin_liquidity",
    "not_shortlisted",
]

#: Why a candidate was put forward, in words a reader can follow. The stored
#: values stay snake_case because they are machine values; these are for prose.
#: Kept in step with ``src/components/recommendations/screening.ts``.
SCREEN_REASON_LABELS: Dict[str, str] = {
    "large_cap": "one of the largest coins you can buy here",
    "deep_drawdown": "trading far below its record high",
    "recent_strength": "among the strongest performers of the past week",
    "next_by_rank": "next largest coin you do not already hold",
}

#: Why a coin was not put forward. Same contract as above.
EXCLUSION_REASON_LABELS: Dict[str, str] = {
    "already_held": "you already hold it",
    "fiat": "it is cash, not a coin",
    "stablecoin": "it is designed to hold a fixed value, so there is nothing to call",
    "duplicate_exposure": "it tracks something you already hold",
    "not_tradeable": "you cannot buy it here in this currency",
    "unranked": "we could not find size or ranking data for it",
    "below_rank_floor": "it is too small for us to look at",
    "thin_liquidity": "too little of it is traded to buy or sell comfortably",
    "not_shortlisted": "it was ranked below the others this time",
}


def screen_reason_label(reason: str) -> str:
    """Reader-facing wording for a screen reason, falling back to the raw value."""
    return SCREEN_REASON_LABELS.get(reason, reason.replace("_", " "))


def exclusion_reason_label(reason: str) -> str:
    """Reader-facing wording for an exclusion reason."""
    return EXCLUSION_REASON_LABELS.get(reason, reason.replace("_", " "))


class Candidate(BaseModel):
    """One asset put forward for assessment."""

    symbol: str
    gecko_id: str
    market_cap_rank: int
    reason: ScreenReason = Field(
        ..., description="Which angle this candidate was drawn from."
    )


class Exclusion(BaseModel):
    """One asset that was considered and set aside, with the reason."""

    symbol: str
    reason: ExclusionReason
    detail: str = ""


def screen(
    universe: Sequence[UniverseRow],
    tradeable: Set[str],
    held: Set[str],
    limit: int = SHORTLIST_SIZE,
) -> Tuple[List[Candidate], List[Exclusion]]:
    """
    Choose which unheld assets to examine this run.

    Args:
        universe: Coins in market-cap order, from the ranked page.
        tradeable: Base symbols the exchange will actually trade right now.
        held: Symbols the user already owns.
        limit: Maximum shortlist size.

    Returns:
        ``(candidates, excluded)``. Both are ordered: candidates by rank, and
        exclusions in the order the universe presented them, so the pair reads
        as an account of the decision rather than a bare answer.
    """
    held_upper = {symbol.upper() for symbol in held}
    tradeable_upper = {symbol.upper() for symbol in tradeable}

    eligible: List[UniverseRow] = []
    excluded: List[Exclusion] = []
    seen: Set[str] = set()

    for row in universe:
        symbol = row.symbol.upper()
        if not symbol or symbol in seen:
            # The ranked page is deduplicated by id, not by ticker. Two coins
            # sharing a ticker is exactly the ambiguity that makes a symbol an
            # unsafe key, so only the higher-ranked one is ever considered.
            continue
        seen.add(symbol)

        reason = _rejection(row, symbol, tradeable_upper, held_upper)
        if reason is not None:
            excluded.append(Exclusion(symbol=symbol, reason=reason[0], detail=reason[1]))
            continue

        eligible.append(row)

    shortlist = _stratified(eligible, limit)
    chosen = {candidate.symbol for candidate in shortlist}

    for row in eligible:
        if row.symbol.upper() not in chosen:
            excluded.append(
                Exclusion(
                    symbol=row.symbol.upper(),
                    reason="not_shortlisted",
                    detail=f"ranked #{row.market_cap_rank} by size",
                )
            )

    logging.info(
        "Screened %d coins to %d candidate(s): %s",
        len(universe),
        len(shortlist),
        ", ".join(f"{c.symbol} ({c.reason})" for c in shortlist) or "none",
    )
    return shortlist, excluded


def _rejection(
    row: UniverseRow,
    symbol: str,
    tradeable: Set[str],
    held: Set[str],
) -> Optional[Tuple[ExclusionReason, str]]:
    """
    Why this coin is not eligible, or ``None`` when it is.

    Ordered cheapest and most decisive first, so the reason a reader is shown is
    the most informative one: "you already hold it" beats "it is too small".
    """
    if symbol in held:
        return "already_held", ""
    if symbol in FIAT_SYMBOLS:
        return "fiat", ""
    if symbol in STABLECOINS:
        return "stablecoin", ""

    tracks = WRAPPED_EQUIVALENTS.get(symbol)
    if tracks is not None and tracks in held:
        return "duplicate_exposure", f"tracks {tracks}, which you hold"
    if tracks is not None:
        return "duplicate_exposure", f"tracks {tracks}"

    if symbol not in tradeable:
        return "not_tradeable", ""

    if row.market_cap_rank is None:
        return "unranked", ""
    if row.market_cap_rank > CANDIDATE_RANK_FLOOR:
        return "below_rank_floor", f"ranked #{row.market_cap_rank} by size"

    if row.total_volume is not None and row.total_volume < MIN_TURNOVER:
        return "thin_liquidity", ""

    return None


def _stratified(eligible: Sequence[UniverseRow], limit: int) -> List[Candidate]:
    """
    Take up to ``limit`` coins, spread across a few named angles.

    One from each angle before a second from any, so a single week's momentum
    cannot fill the whole shortlist. Whatever is left over is filled by size,
    which is the most defensible tie-break available and keeps the result
    stable between runs.
    """
    if limit < 1 or not eligible:
        return []

    by_rank = sorted(eligible, key=lambda row: (row.market_cap_rank or 10**9, row.symbol))
    strata = _strata(by_rank)

    chosen: List[Candidate] = []
    taken: Set[str] = set()

    for reason, rows in strata:
        for row in rows:
            if len(chosen) >= limit:
                break
            if row.symbol.upper() in taken:
                continue
            taken.add(row.symbol.upper())
            chosen.append(_candidate(row, reason))
            break  # one per angle on the first pass

    for row in by_rank:
        if len(chosen) >= limit:
            break
        if row.symbol.upper() in taken:
            continue
        taken.add(row.symbol.upper())
        chosen.append(_candidate(row, "next_by_rank"))

    return sorted(chosen, key=lambda c: c.market_cap_rank)


def _strata(by_rank: Sequence[UniverseRow]) -> List[Tuple[ScreenReason, List[UniverseRow]]]:
    """The named angles, each already ordered by preference within itself."""
    large_cap = [
        row for row in by_rank if (row.market_cap_rank or 10**9) <= LARGE_CAP_RANK
    ]

    drawdowns = [row.ath_change_pct for row in by_rank if row.ath_change_pct is not None]
    deep: List[UniverseRow] = []
    if drawdowns:
        midpoint = statistics.median(drawdowns)
        # More negative than the middle of the pool: furthest below its peak.
        deep = sorted(
            (
                row
                for row in by_rank
                if row.ath_change_pct is not None and row.ath_change_pct < midpoint
            ),
            key=lambda row: row.ath_change_pct or 0.0,
        )

    weekly = sorted(row.change_7d_pct for row in by_rank if row.change_7d_pct is not None)
    strong: List[UniverseRow] = []
    if weekly:
        cutoff = weekly[min(int(len(weekly) * RECENT_STRENGTH_QUANTILE), len(weekly) - 1)]
        strong = sorted(
            (row for row in by_rank if (row.change_7d_pct or float("-inf")) >= cutoff),
            key=lambda row: row.change_7d_pct or 0.0,
            reverse=True,
        )

    return [
        ("large_cap", large_cap),
        ("deep_drawdown", deep),
        ("recent_strength", strong),
    ]


def _candidate(row: UniverseRow, reason: ScreenReason) -> Candidate:
    return Candidate(
        symbol=row.symbol.upper(),
        gecko_id=row.gecko_id,
        market_cap_rank=row.market_cap_rank or 0,
        reason=reason,
    )
