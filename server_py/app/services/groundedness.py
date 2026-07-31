"""
Server-side groundedness check.

The prompt asks the model to cite only fields that exist and to copy their
values verbatim. This module is what makes that true rather than hoped for: it
re-reads every claim against the grounding context and reconciles the two.

Four outcomes per claim:

``unknown_metric``
    The cited field is not in the context at all. The claim is **dropped** --
    an untraceable fact has no place in the payload, whatever it says.
``cited_unavailable_metric``
    The field exists but was not computed this run. Also dropped: the model
    invented a value for a gap it was explicitly shown.
``value_mismatch`` / ``text_mismatch``
    The field exists and was computed, but the model's transcription differs.
    The claim is kept and its value **corrected to the context value**, so the
    payload can never carry a number the app did not measure, and the
    discrepancy is recorded.

Any violation costs confidence. The caller retries once, and if the second
attempt still fails the check, the recommendation is downgraded rather than
served at face value.
"""

import re
from typing import Dict, List, Optional, Tuple

from ..schemas.grounding import Metric, RecommendationContext
from ..schemas.recommendation import (
    GroundednessViolation,
    ModelPayload,
    ModelSupportingFact,
    SupportingFact,
)

#: Relative tolerance when comparing a quoted number against the context. Wide
#: enough to forgive display rounding, narrow enough that a fabricated figure
#: cannot hide inside it.
RELATIVE_TOLERANCE = 0.005
ABSOLUTE_TOLERANCE = 0.01

#: Characters stripped before parsing: currency symbols, thousands separators,
#: percent signs and the like.
_STRIP_PATTERN = re.compile(r"[£$€,%\s+]")
_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

#: Values that mean "this field had nothing in it".
_UNAVAILABLE_WORDS = {"unavailable", "n/a", "na", "none", "null", "-", "—"}


class CheckOutcome:
    """Verified facts plus the record of what had to be changed."""

    __slots__ = ("facts", "violations", "checked", "dropped", "corrected")

    def __init__(self) -> None:
        self.facts: Dict[str, List[SupportingFact]] = {}
        self.violations: List[GroundednessViolation] = []
        self.checked = 0
        self.dropped = 0
        self.corrected = 0

    @property
    def passed(self) -> bool:
        return not self.violations

    def violations_for(self, symbol: str) -> List[GroundednessViolation]:
        return [violation for violation in self.violations if violation.symbol == symbol]


def parse_number(raw: str) -> Optional[float]:
    """
    Pull a single number out of a value string.

    Returns ``None`` when the string carries no number at all -- which, for a
    metric that *has* a numeric value, is itself a mismatch rather than a pass.
    """
    if raw is None:
        return None
    cleaned = _STRIP_PATTERN.sub("", str(raw))
    match = _NUMBER_PATTERN.search(cleaned)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def values_agree(quoted: float, actual: float) -> bool:
    """Compare within a tolerance that scales with the magnitude of the value."""
    tolerance = max(abs(actual) * RELATIVE_TOLERANCE, ABSOLUTE_TOLERANCE)
    return abs(quoted - actual) <= tolerance


def _looks_unavailable(raw: str) -> bool:
    return str(raw).strip().lower() in _UNAVAILABLE_WORDS


def _verified_fact(metric: Metric, fact: ModelSupportingFact) -> SupportingFact:
    return SupportingFact(
        metric=metric.field,
        label=metric.label,
        value=metric.rendered(),
        unit=metric.unit,
        interpretation=fact.interpretation,
        verified=True,
    )


def check(payload: ModelPayload, context: RecommendationContext) -> CheckOutcome:
    """Verify every supporting fact in ``payload`` against ``context``."""
    index = context.metric_index()
    outcome = CheckOutcome()

    for recommendation in payload.recommendations:
        symbol = recommendation.symbol.upper()
        kept: List[SupportingFact] = []

        for fact in recommendation.supporting_facts:
            outcome.checked += 1
            metric = index.get(fact.metric)

            if metric is None:
                outcome.dropped += 1
                outcome.violations.append(
                    GroundednessViolation(
                        symbol=symbol,
                        metric=fact.metric,
                        kind="unknown_metric",
                        detail="cited a field that is not in the grounding context",
                        model_value=fact.value,
                    )
                )
                continue

            if not metric.is_available:
                # Quoting an unavailable field back as "unavailable" is honest
                # reporting, not a violation -- but it carries no evidence, so
                # it still does not become a supporting fact.
                if _looks_unavailable(fact.value):
                    outcome.dropped += 1
                    continue

                outcome.dropped += 1
                outcome.violations.append(
                    GroundednessViolation(
                        symbol=symbol,
                        metric=fact.metric,
                        kind="cited_unavailable_metric",
                        detail="stated a value for a field marked unavailable",
                        model_value=fact.value,
                        context_value="unavailable",
                    )
                )
                continue

            if metric.text is not None:
                if str(fact.value).strip().lower() == metric.text.strip().lower():
                    kept.append(_verified_fact(metric, fact))
                else:
                    outcome.corrected += 1
                    outcome.violations.append(
                        GroundednessViolation(
                            symbol=symbol,
                            metric=fact.metric,
                            kind="text_mismatch",
                            detail="quoted a different category than the context holds",
                            model_value=str(fact.value),
                            context_value=metric.text,
                        )
                    )
                    corrected = _verified_fact(metric, fact)
                    corrected.verified = False
                    corrected.model_stated_value = str(fact.value)
                    kept.append(corrected)
                continue

            quoted = parse_number(fact.value)
            if quoted is None:
                outcome.corrected += 1
                outcome.violations.append(
                    GroundednessViolation(
                        symbol=symbol,
                        metric=fact.metric,
                        kind="unparsable_value",
                        detail="quoted no readable number for a numeric field",
                        model_value=str(fact.value),
                        context_value=metric.rendered(),
                    )
                )
                corrected = _verified_fact(metric, fact)
                corrected.verified = False
                corrected.model_stated_value = str(fact.value)
                kept.append(corrected)
                continue

            if metric.value is not None and values_agree(quoted, metric.value):
                kept.append(_verified_fact(metric, fact))
                continue

            outcome.corrected += 1
            outcome.violations.append(
                GroundednessViolation(
                    symbol=symbol,
                    metric=fact.metric,
                    kind="value_mismatch",
                    detail="quoted a value that does not match the grounding context",
                    model_value=str(fact.value),
                    context_value=metric.rendered(),
                )
            )
            corrected = _verified_fact(metric, fact)
            corrected.verified = False
            corrected.model_stated_value = str(fact.value)
            kept.append(corrected)

        outcome.facts[symbol] = kept

    return outcome


def feedback_for(outcome: CheckOutcome) -> str:
    """
    A correction message for the retry attempt.

    Names each offending citation explicitly. A vague "some of your numbers
    were wrong" invites the model to rewrite everything, including the parts
    that were right.
    """
    lines = ["Your previous answer failed verification against the grounding context:"]
    for violation in outcome.violations:
        if violation.kind == "unknown_metric":
            lines.append(
                f"- {violation.symbol}: '{violation.metric}' is not a field in the "
                "context. Cite only fields that appear there."
            )
        elif violation.kind == "cited_unavailable_metric":
            lines.append(
                f"- {violation.symbol}: '{violation.metric}' is marked unavailable, but you "
                f"stated '{violation.model_value}'. Do not supply values for unavailable "
                "fields; treat them as a reason to lower confidence."
            )
        else:
            lines.append(
                f"- {violation.symbol}: '{violation.metric}' is "
                f"'{violation.context_value}' in the context, but you wrote "
                f"'{violation.model_value}'. Copy values exactly."
            )
    lines.append(
        "Return the corrected answer in the same schema. Every supporting fact must "
        "name a field from the context and copy its value character for character."
    )
    return "\n".join(lines)


def pick_better(first: CheckOutcome, second: CheckOutcome) -> Tuple[CheckOutcome, bool]:
    """
    Choose between the original and the retry.

    Returns the outcome to serve and whether the retry was the one used. Fewer
    violations wins; a tie keeps the retry, since it was produced with the
    specific corrections in hand.
    """
    if len(second.violations) <= len(first.violations):
        return second, True
    return first, False
