"""
The recommendation output contract.

``ModelRecommendation`` / ``ModelPayload`` are what the language model is
allowed to return -- validated the moment it responds, so a malformed or
prose-shaped answer fails loudly at the seam rather than halfway down the UI.

``RecommendationResponse`` is what the API actually serves. It is deliberately
*not* the model's output: the disclaimer, the verification report and the final
confidence are all attached server-side, after the model has had its say.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

try:  # pragma: no cover
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal  # type: ignore

from .grounding import Confidence, RecommendationContext

Action = Literal["buy", "sell", "hold"]


# ---------------------------------------------------------------------------
# What the model returns
# ---------------------------------------------------------------------------


class ModelSupportingFact(BaseModel):
    """One claim, tied to one metric in the grounding context."""

    metric: str = Field(..., description="Exact `field` name from the grounding context.")
    value: str = Field(..., description="The value copied verbatim from that field.")
    interpretation: str = Field(..., description="What this value implies, in one sentence.")


class ModelRecommendation(BaseModel):
    symbol: str
    recommendation: Action
    confidence: Confidence
    confidence_rationale: str
    supporting_facts: List[ModelSupportingFact] = []
    risks_or_caveats: List[str] = []


class ModelPayload(BaseModel):
    """The full structured response expected from a single model call."""

    summary: str
    recommendations: List[ModelRecommendation] = []


# ---------------------------------------------------------------------------
# What the API serves
# ---------------------------------------------------------------------------


class SupportingFact(BaseModel):
    """
    A verified claim.

    ``value`` is always the value held in the grounding context, never the
    model's transcription of it: when verification finds a mismatch the value
    is *corrected* here and ``verified`` is set to false, so the payload can
    never carry a number the app did not actually measure.
    """

    metric: str
    label: str
    value: str
    unit: str = ""
    interpretation: str
    #: What this metric measures, in plain words, from the metric catalogue.
    #: Written in code rather than by the model: a definition is a fixed fact
    #: about the metric, so it should not vary between runs.
    plain: str = ""
    verified: bool = True
    #: Set when the model quoted something other than the context value.
    model_stated_value: Optional[str] = None


class AssetRecommendation(BaseModel):
    symbol: str
    recommendation: Action
    confidence: Confidence
    confidence_rationale: str
    #: Confidence the model reported before the server applied the data
    #: ceiling and any verification penalty. Kept for calibration analysis.
    model_confidence: Confidence
    confidence_ceiling: Confidence
    ceiling_reason: str
    supporting_facts: List[SupportingFact] = []
    risks_or_caveats: List[str] = []
    data_completeness: float = 0.0
    categories_available: List[str] = []
    categories_missing: List[str] = []
    #: Set when verification changed something about this recommendation.
    verification_note: Optional[str] = None


class GroundednessViolation(BaseModel):
    symbol: str
    metric: str
    kind: Literal[
        "unknown_metric",
        "cited_unavailable_metric",
        "value_mismatch",
        "text_mismatch",
        "unparsable_value",
    ]
    detail: str
    model_value: Optional[str] = None
    context_value: Optional[str] = None


class GroundednessReport(BaseModel):
    """Result of checking the model's claims against the grounding context."""

    status: Literal["verified", "corrected"] = "verified"
    facts_checked: int = 0
    facts_dropped: int = 0
    facts_corrected: int = 0
    #: True when a second model call was made after the first failed checks.
    retried: bool = False
    confidence_downgraded: bool = False
    violations: List[GroundednessViolation] = []


class RecommendationResponse(BaseModel):
    """The payload served by ``/api/recommendations/``."""

    status: Literal["ok", "empty", "unavailable"] = "ok"
    #: Set for ``empty`` and ``unavailable``; the UI shows it in place of the
    #: recommendation list.
    message: Optional[str] = None
    generated_at: str
    quote_currency: str = "GBP"
    summary: str = ""
    recommendations: List[AssetRecommendation] = []
    #: Injected server-side, after the model call. The model is never trusted
    #: to produce it, and it is never assembled from model output.
    disclaimer: str = ""
    groundedness: GroundednessReport = GroundednessReport()
    #: The grounding data itself, so the UI can show the evidence behind a call
    #: and a reader can audit any claim without re-running the pipeline.
    context: Optional[RecommendationContext] = None
    sources: Dict[str, str] = {}
