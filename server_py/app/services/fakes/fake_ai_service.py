"""
In-process stand-in for AIService.

Serves a fixed markdown recommendation so the AI flow can be exercised end to
end without an OpenAI API key or an outbound request.
"""

import asyncio
from typing import Any, Dict, List

from . import fixtures, scenarios
from .scenarios import Scenario


class FakeAIService:
    """Scenario-aware fake implementing the AIService interface."""

    def __init__(self, scenario: Scenario = None) -> None:
        self.scenario = scenario or Scenario.parse(None)

    async def get_recommendations(
        self,
        portfolio: List[Dict[str, Any]],
        market_data: List[Dict[str, Any]],
    ) -> str:
        if self.scenario.has(scenarios.SLOW_AI):
            await asyncio.sleep(scenarios.SLOW_DELAY_SECONDS)

        if self.scenario.has(scenarios.ERROR_AI):
            # Hard failure: surfaces to the client as a 500 from the router.
            raise RuntimeError("Simulated OpenAI API failure")

        if self.scenario.has(scenarios.DEGRADED_AI):
            # Soft failure: mirrors AIService's own graceful fallback string,
            # which arrives as a 200 with unhelpful content.
            return fixtures.RECOMMENDATIONS_UNAVAILABLE

        return fixtures.RECOMMENDATIONS_MARKDOWN
