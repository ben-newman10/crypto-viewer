"""
The grounding context: the complete, typed set of facts the model may use.

Two rules shape this module.

1. **Nothing outside this object may be stated by the model.** Every metric
   carries a ``field`` name, and the model is required to cite that exact name
   for every claim it makes. The server-side groundedness check (see
   ``services/groundedness.py``) then re-verifies each cited value against the
   metric it names, so a fabricated number is caught rather than trusted.

2. **A gap is data, not an absence.** When a metric cannot be computed -- not
   enough candles for a 200-period average, an upstream source that failed --
   the metric is still present with ``status="unavailable"`` and a reason. The
   model has to see the hole in order to react to it by lowering confidence,
   and the deterministic confidence ceiling below is derived from exactly these
   gaps.
"""

from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

try:  # pragma: no cover - typing_extensions is a pydantic dependency anyway
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal  # type: ignore

MetricStatus = Literal["available", "unavailable"]
Confidence = Literal["low", "medium", "high"]

# Confidence levels, weakest first. Used for clamping.
CONFIDENCE_ORDER: List[str] = ["low", "medium", "high"]


# ---------------------------------------------------------------------------
# Signal categories
# ---------------------------------------------------------------------------
# The confidence rubric is expressed in terms of *independent signal
# categories* rather than individual metrics, so that four momentum readings
# agreeing with one another does not masquerade as four independent
# confirmations.

CATEGORY_TREND = "trend"
CATEGORY_MOMENTUM = "momentum"
CATEGORY_VOLATILITY = "volatility"
CATEGORY_SENTIMENT = "sentiment"
CATEGORY_MARKET_STRUCTURE = "market_structure"
CATEGORY_POSITION = "position"

SIGNAL_CATEGORIES: List[str] = [
    CATEGORY_TREND,
    CATEGORY_MOMENTUM,
    CATEGORY_VOLATILITY,
    CATEGORY_SENTIMENT,
    CATEGORY_MARKET_STRUCTURE,
]


class Metric(BaseModel):
    """
    A single citable fact.

    ``field`` is the identifier the model must quote; ``value`` (numeric) and
    ``text`` (categorical) are mutually exclusive in practice. Exactly one of
    them is set when ``status`` is ``available``, and neither is set when it is
    ``unavailable``.
    """

    field: str = Field(..., description="Exact identifier the model must cite.")
    label: str = Field(..., description="Human-readable name for the UI.")
    category: str = Field(..., description="Signal category this metric belongs to.")
    status: MetricStatus = "available"
    value: Optional[float] = None
    text: Optional[str] = None
    unit: str = ""
    note: Optional[str] = Field(
        None,
        description="How it was computed, or why it is unavailable.",
    )

    @property
    def is_available(self) -> bool:
        return self.status == "available"

    def rendered(self) -> str:
        """
        The value as the model is expected to quote it back.

        Precision scales with magnitude so that a price keeps its pence and a
        MACD histogram near zero keeps its significant digits. Both the prompt
        and the verification step use this same rendering, so "copy it exactly"
        is an instruction the model can actually follow.
        """
        if not self.is_available:
            return "unavailable"
        if self.text is not None:
            return self.text
        if self.value is None:
            return "unavailable"

        magnitude = abs(self.value)
        if magnitude >= 1000:
            text = f"{self.value:.2f}"
        elif magnitude >= 1:
            text = f"{self.value:.4f}"
        else:
            text = f"{self.value:.6f}"

        return text.rstrip("0").rstrip(".") if "." in text else text


class DataCompleteness(BaseModel):
    """How much of the intended grounding data actually arrived."""

    available: int
    total: int
    ratio: float
    categories_available: List[str] = []
    categories_missing: List[str] = []


class AssetContext(BaseModel):
    """Everything known about one holding."""

    symbol: str
    product_id: str
    metrics: List[Metric] = []
    completeness: DataCompleteness
    #: Deterministic upper bound on confidence, derived from completeness
    #: alone. The model's self-reported confidence is clamped to this by the
    #: server -- thin data cannot produce a confident call, whatever the model
    #: says.
    confidence_ceiling: Confidence = "high"
    #: Reason for the ceiling, surfaced in the response so the UI can explain
    #: why a call is only as confident as it is.
    ceiling_reason: str = ""


class RecommendationContext(BaseModel):
    """The complete grounding context for one recommendation run."""

    generated_at: str
    quote_currency: str = "GBP"
    assets: List[AssetContext] = []
    #: Portfolio- and market-wide metrics, citable by every asset.
    shared_metrics: List[Metric] = []
    #: Sources that were consulted and whether they answered.
    sources: Dict[str, str] = {}

    def metric_index(self) -> Dict[str, Metric]:
        """Flat ``field -> Metric`` map used to verify the model's citations."""
        index: Dict[str, Metric] = {metric.field: metric for metric in self.shared_metrics}
        for asset in self.assets:
            for metric in asset.metrics:
                index[metric.field] = metric
        return index

    def asset(self, symbol: str) -> Optional[AssetContext]:
        for candidate in self.assets:
            if candidate.symbol.upper() == symbol.upper():
                return candidate
        return None


# ---------------------------------------------------------------------------
# The confidence rubric
# ---------------------------------------------------------------------------
# Written once, here, and used in three places: the system prompt (so the model
# rates itself against it), the deterministic ceiling below (so the rating can
# never outrun the data), and the API response (so a reader can check the call
# against the same yardstick).

CONFIDENCE_RUBRIC = """\
high
  At least three independent signal categories are available AND at least
  three of them point the same way AND no available category directly
  contradicts the call AND data completeness is at least 0.80.
medium
  At least two independent signal categories are available, a majority of the
  available categories agree, and data completeness is at least 0.50.
low
  Fewer than two signal categories are available, OR the available categories
  disagree with one another, OR data completeness is below 0.50, OR the call
  rests mainly on a single metric.

Signal categories are: trend (moving averages and their crossover state),
momentum (RSI, MACD), volatility (realised volatility, drawdown from the
period high), sentiment (Fear & Greed Index), and market structure (market
cap, circulating supply, distance from all-time high).\
"""

#: Completeness thresholds backing the rubric. Chosen to match the wording
#: above; changing one means changing both.
HIGH_COMPLETENESS = 0.80
MEDIUM_COMPLETENESS = 0.50
HIGH_MIN_CATEGORIES = 3
MEDIUM_MIN_CATEGORIES = 2


def confidence_ceiling(completeness: DataCompleteness) -> Tuple[str, str]:
    """
    Highest confidence the data alone can support, with the reason.

    This is the enforcement half of the rubric. The prompt asks the model to
    lower its confidence when data is thin; this makes sure it happens whether
    or not the model complies.
    """
    category_count = len(completeness.categories_available)

    if category_count < MEDIUM_MIN_CATEGORIES or completeness.ratio < MEDIUM_COMPLETENESS:
        return (
            "low",
            f"only {category_count} signal "
            f"{'category' if category_count == 1 else 'categories'} available and "
            f"{completeness.ratio:.0%} of grounding data present",
        )

    if category_count < HIGH_MIN_CATEGORIES or completeness.ratio < HIGH_COMPLETENESS:
        return (
            "medium",
            f"{category_count} signal categories available and "
            f"{completeness.ratio:.0%} of grounding data present",
        )

    return (
        "high",
        f"{category_count} signal categories available and "
        f"{completeness.ratio:.0%} of grounding data present",
    )


def clamp_confidence(reported: str, ceiling: str) -> str:
    """Return the weaker of the model's confidence and the data's ceiling."""
    try:
        return CONFIDENCE_ORDER[
            min(CONFIDENCE_ORDER.index(reported), CONFIDENCE_ORDER.index(ceiling))
        ]
    except ValueError:  # unrecognised value: fail safe, not loud
        return "low"


def downgrade(confidence: str, steps: int = 1) -> str:
    """Lower a confidence rating, never below ``low``."""
    try:
        index = CONFIDENCE_ORDER.index(confidence)
    except ValueError:
        return "low"
    return CONFIDENCE_ORDER[max(0, index - steps)]


def summarise_completeness(metrics: List[Metric]) -> DataCompleteness:
    """Build a :class:`DataCompleteness` from a flat list of metrics."""
    scored = [metric for metric in metrics if metric.category in SIGNAL_CATEGORIES]
    available = [metric for metric in scored if metric.is_available]

    categories_available = sorted(
        {metric.category for metric in available if metric.category in SIGNAL_CATEGORIES}
    )
    categories_missing = [
        category for category in SIGNAL_CATEGORIES if category not in categories_available
    ]

    total = len(scored)
    return DataCompleteness(
        available=len(available),
        total=total,
        ratio=(len(available) / total) if total else 0.0,
        categories_available=categories_available,
        categories_missing=categories_missing,
    )
