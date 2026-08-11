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

#: Why an asset is in the context at all. A ``holding`` is one the reader owns;
#: a ``candidate`` is one the app put forward for assessment. The distinction is
#: the server's to make, never the model's -- it decides which calls are even
#: meaningful (you cannot sell what you do not own) and it must not vary with a
#: generation.
AssetRole = Literal["holding", "candidate"]

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
#: Always-present facts (the current price, how many candles arrived). Citable,
#: but excluded from the completeness ratio: counting them would inflate the
#: score for an asset whose actual signals are all missing.
CATEGORY_REFERENCE = "reference"

SIGNAL_CATEGORIES: List[str] = [
    CATEGORY_TREND,
    CATEGORY_MOMENTUM,
    CATEGORY_VOLATILITY,
    CATEGORY_SENTIMENT,
    CATEGORY_MARKET_STRUCTURE,
]

#: How a category is named to a reader. The stored values stay snake_case
#: because the API serves them as machine values; these are for prose only.
CATEGORY_LABELS: Dict[str, str] = {
    CATEGORY_TREND: "price trend",
    CATEGORY_MOMENTUM: "momentum",
    CATEGORY_VOLATILITY: "price swings",
    CATEGORY_SENTIMENT: "market mood",
    CATEGORY_MARKET_STRUCTURE: "market size",
    CATEGORY_POSITION: "your holding",
    CATEGORY_REFERENCE: "reference data",
}


def category_label(category: str) -> str:
    """Reader-facing name for a signal category, falling back to the raw value."""
    return CATEGORY_LABELS.get(category, category.replace("_", " "))


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
    #: Novice-facing definition of what this metric measures, from the metric
    #: catalogue. Distinct from ``note``, which is about *this* run -- the
    #: method used, or the reason the value is missing. Never sent to the model.
    plain: str = Field(
        "",
        description="What this measures, in words a first-time reader can follow.",
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
    """Everything known about one asset in the run."""

    symbol: str
    product_id: str
    #: Defaults to ``holding`` so that every existing caller keeps its meaning:
    #: before candidates existed, every asset in a context was one.
    role: AssetRole = "holding"
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

    def holdings(self) -> List[AssetContext]:
        """Assets the reader owns, in the order they appear."""
        return [asset for asset in self.assets if asset.role == "holding"]

    def candidates(self) -> List[AssetContext]:
        """Assets the reader does not own, put forward for assessment."""
        return [asset for asset in self.assets if asset.role == "candidate"]


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
    reason = _ceiling_reason(category_count, completeness.ratio)

    if category_count < MEDIUM_MIN_CATEGORIES or completeness.ratio < MEDIUM_COMPLETENESS:
        return "low", reason

    if category_count < HIGH_MIN_CATEGORIES or completeness.ratio < HIGH_COMPLETENESS:
        return "medium", reason

    return "high", reason


def _ceiling_reason(category_count: int, ratio: float) -> str:
    """
    The ceiling explained to a reader rather than to an analyst.

    "3 signal categories available and 85% of grounding data present" is
    accurate but means nothing to someone who has not read the rubric, so it is
    phrased as a fraction of what the app looks for and what actually arrived.
    """
    total = len(SIGNAL_CATEGORIES)
    was_were = "was" if category_count == 1 else "were"
    only = "only " if category_count < total else ""
    return (
        f"{only}{category_count} of the {total} kinds of signal we look at "
        f"{was_were} available, and {ratio:.0%} of the data we wanted arrived"
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
