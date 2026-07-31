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

from ...schemas.grounding import AssetContext, Metric, RecommendationContext
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
        rationale = (
            f"{call['confidence']}: {len(asset.completeness.categories_available)} signal "
            f"categories available at {asset.completeness.ratio:.0%} data completeness"
        )
        if missing:
            rationale += f"; no {' or '.join(missing)} data this pass"

        caveats = [
            "A move outside the recent range would invalidate the trend reading.",
        ]
        if missing:
            caveats.append(
                f"Unavailable this pass: {', '.join(missing)}. Those signals could point "
                "the other way."
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
                interpretation=f"{metric.label} for {asset.symbol}.",
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
                    interpretation=f"{first.label} for {asset.symbol}.",
                )
            facts.append(
                ModelSupportingFact(
                    metric=f"{asset.symbol}.exchange_netflow_7d",
                    value="-12400",
                    interpretation="Coins are leaving exchanges, which is bullish.",
                )
            )

        return facts
