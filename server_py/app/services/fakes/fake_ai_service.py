"""
In-process stand-in for AIService.

Returns a *structured* payload matching the real schema, not prose -- so the
E2E suite exercises the same validation, verification and rendering path as a
live model call.

The important detail: supporting facts are read out of the grounding context
the fake is handed, not from a fixture of their own. That means the
groundedness check in front of the UI is doing real work in tests -- and the
``ungrounded-ai`` scenario, which deliberately quotes a number that is not in
the context, actually gets caught by it.
"""

import asyncio
from typing import List, Optional

from ...schemas.grounding import (
    AssetContext,
    Metric,
    RecommendationContext,
    category_label,
)
from ...schemas.recommendation import ModelPayload, ModelRecommendation, ModelSupportingFact
from ..ai_errors import AIUnavailableError
from . import fixtures, scenarios
from .scenarios import Scenario

#: Categories a fact is drawn from, most informative first. Mirrors what a
#: well-behaved model would cite: a spread across independent signal
#: categories rather than four readings of the same thing.
_FACT_PRIORITY = ["trend", "momentum", "volatility", "sentiment", "market_structure", "position"]

#: How many supporting facts the fake cites per asset.
_FACTS_PER_ASSET = 4


def _plain_interpretation(metric: Metric, symbol: str) -> str:
    """
    A stand-in for the model's own sentence about one figure.

    Written in the register the real prompt now asks for -- plain, addressed to
    a reader with no trading background, and naming the metric in words rather
    than by its field id -- so the E2E suite renders text shaped like what
    production actually serves.
    """
    return (
        f"This is what the {category_label(metric.category)} reading for {symbol} "
        "looks like at the moment."
    )


class FakeAIService:
    """Scenario-aware fake implementing the AIService interface."""

    #: Surfaced in the recommendation log the same way the real service's is.
    model = "fake-structured-model"

    def __init__(self, scenario: Scenario = None) -> None:
        self.scenario = scenario or Scenario.parse(None)

    async def generate(
        self,
        context: RecommendationContext,
        feedback: Optional[str] = None,
    ) -> ModelPayload:
        if self.scenario.has(scenarios.SLOW_AI):
            await asyncio.sleep(scenarios.SLOW_DELAY_SECONDS)

        if self.scenario.has(scenarios.ERROR_AI):
            # Hard failure: surfaces to the client as a 500 from the router.
            raise RuntimeError("Simulated OpenAI API failure")

        if self.scenario.has(scenarios.DEGRADED_AI):
            # Soft failure: the pipeline degrades to a 200 carrying an
            # explanation instead of recommendations.
            raise AIUnavailableError(
                "Unable to generate recommendations at this time. Please try again later."
            )

        # Deliberately ungrounded on every attempt, retry included, so the
        # correction-and-downgrade path is exercised rather than just the retry.
        ungrounded = self.scenario.has(scenarios.UNGROUNDED_AI)

        return ModelPayload(
            summary=fixtures.FAKE_SUMMARY,
            recommendations=[
                self._for_asset(asset, ungrounded=ungrounded, shared=context.shared_metrics)
                for asset in context.assets
            ],
        )

    def _for_asset(
        self,
        asset: AssetContext,
        ungrounded: bool,
        shared: List[Metric],
    ) -> ModelRecommendation:
        call = fixtures.FAKE_CALLS.get(
            asset.symbol, {"recommendation": "hold", "confidence": "medium"}
        )
        facts = self._facts(asset, shared, ungrounded=ungrounded)

        missing = asset.completeness.categories_missing
        available_count = len(asset.completeness.categories_available)
        rationale = (
            f"We had {available_count} of the kinds of information we look for, and "
            f"{asset.completeness.ratio:.0%} of the readings we wanted came through"
        )
        if missing:
            plain_missing = [category_label(category) for category in missing]
            rationale += f", but nothing on {' or '.join(plain_missing)}"
        rationale += "."

        caveats = [
            "If the price moves outside the range it has held recently, this reading "
            "no longer applies.",
        ]
        if missing:
            caveats.append(
                f"We had no {', '.join(category_label(c) for c in missing)} data this "
                "time, and it could point the other way."
            )

        return ModelRecommendation(
            symbol=asset.symbol,
            recommendation=call["recommendation"],
            confidence=call["confidence"],
            confidence_rationale=rationale,
            supporting_facts=facts,
            risks_or_caveats=caveats,
        )

    def _facts(
        self,
        asset: AssetContext,
        shared: List[Metric],
        ungrounded: bool,
    ) -> List[ModelSupportingFact]:
        available = [
            metric
            for metric in list(asset.metrics) + list(shared)
            if metric.is_available and metric.category in _FACT_PRIORITY
        ]

        # One fact per category before a second from any category, so the
        # evidence spans independent signals rather than restating one of them
        # four times -- which is what the confidence rubric rewards.
        chosen: List[Metric] = []
        for category in _FACT_PRIORITY:
            for metric in available:
                if metric.category == category:
                    chosen.append(metric)
                    break
            if len(chosen) == _FACTS_PER_ASSET:
                break
        facts = [
            ModelSupportingFact(
                metric=metric.field,
                value=metric.rendered(),
                interpretation=_plain_interpretation(metric, asset.symbol),
            )
            for metric in chosen
        ]

        if ungrounded and facts:
            # A plausible-looking but fabricated number, and a citation of a
            # field that does not exist. Both are what the check is for.
            first = chosen[0]
            if first.value is not None:
                facts[0] = ModelSupportingFact(
                    metric=first.field,
                    value=f"{first.value * 1.4:.4f}",
                    interpretation=_plain_interpretation(first, asset.symbol),
                )
            facts.append(
                ModelSupportingFact(
                    metric=f"{asset.symbol}.exchange_netflow_7d",
                    value="-12400",
                    interpretation="Coins are leaving exchanges, which is bullish.",
                )
            )

        return facts
