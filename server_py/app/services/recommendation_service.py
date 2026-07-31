"""
Orchestration for a single recommendation run.

The sequence, and why it is in this order:

1. **Build the grounding context** -- indicators computed in code, gaps marked
   explicitly.
2. **Ask the model**, with that context as a closed field list.
3. **Verify** every claim against the context. On any violation, retry once
   with the specific corrections named.
4. **Reconcile**: correct or drop unverified facts, clamp confidence to what
   the data can support, and downgrade further if verification still failed.
5. **Inject the disclaimer** -- a server-side constant, never model output.
6. **Log** context, model output and check result, so the confidence rating can
   be checked against reality later instead of taken on trust.

Steps 3-5 are what make the pipeline more than a well-written prompt.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..config import DISCLAIMER
from ..schemas import to_dict
from ..schemas.grounding import RecommendationContext, clamp_confidence, downgrade
from ..schemas.recommendation import (
    AssetRecommendation,
    GroundednessReport,
    ModelPayload,
    RecommendationResponse,
)
from . import groundedness, recommendation_log
from .ai_errors import AIUnavailableError
from .context_builder import ContextBuilder

EMPTY_PORTFOLIO_MESSAGE = "No cryptocurrency holdings found in your portfolio."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_response(context: Optional[RecommendationContext] = None) -> RecommendationResponse:
    return RecommendationResponse(
        status="empty",
        message=EMPTY_PORTFOLIO_MESSAGE,
        generated_at=context.generated_at if context else _now(),
        quote_currency=context.quote_currency if context else "GBP",
        disclaimer=DISCLAIMER,
        sources=context.sources if context else {},
    )


def _unavailable_response(
    message: str,
    context: Optional[RecommendationContext] = None,
) -> RecommendationResponse:
    return RecommendationResponse(
        status="unavailable",
        message=message,
        generated_at=context.generated_at if context else _now(),
        quote_currency=context.quote_currency if context else "GBP",
        disclaimer=DISCLAIMER,
        context=context,
        sources=context.sources if context else {},
    )


async def generate(
    coinbase_service,
    ai_service,
    market_context_service=None,
    quote_currency: str = "GBP",
) -> RecommendationResponse:
    """Run the full pipeline and return the payload the API serves."""
    context = await ContextBuilder(coinbase_service, market_context_service).build(
        quote_currency=quote_currency
    )

    if not context.assets:
        return _empty_response(context)

    try:
        payload = await ai_service.generate(context)
    except AIUnavailableError as error:
        logging.warning("Recommendation unavailable: %s", error)
        return _unavailable_response(str(error), context)

    outcome = groundedness.check(payload, context)
    retried = False

    if not outcome.passed:
        logging.info(
            "Groundedness check found %d violation(s); retrying once",
            len(outcome.violations),
        )
        try:
            retry_payload = await ai_service.generate(
                context, feedback=groundedness.feedback_for(outcome)
            )
        except AIUnavailableError as error:
            # The first answer is still usable once its bad claims are handled.
            logging.warning("Groundedness retry failed: %s", error)
        else:
            retry_outcome = groundedness.check(retry_payload, context)
            better, used_retry = groundedness.pick_better(outcome, retry_outcome)
            if used_retry:
                payload, outcome, retried = retry_payload, better, True
            else:
                outcome = better

    response = _assemble(context, payload, outcome, retried)

    recommendation_log.record(
        context=context,
        response=response,
        model_payload=to_dict(payload),
        groundedness=response.groundedness,
        model_name=getattr(ai_service, "model", "unknown"),
    )

    return response


def _assemble(
    context: RecommendationContext,
    payload: ModelPayload,
    outcome: "groundedness.CheckOutcome",
    retried: bool,
) -> RecommendationResponse:
    """Turn a verified model payload into the served response."""
    report = GroundednessReport(
        status="verified" if outcome.passed else "corrected",
        facts_checked=outcome.checked,
        facts_dropped=outcome.dropped,
        facts_corrected=outcome.corrected,
        retried=retried,
        confidence_downgraded=False,
        violations=outcome.violations,
    )

    recommendations = []
    any_downgrade = False

    for item in payload.recommendations:
        symbol = item.symbol.upper()
        asset = context.asset(symbol)
        if asset is None:
            # The model invented an asset that is not in the portfolio. There is
            # no context to verify it against, so it is not served at all.
            logging.warning("Dropping recommendation for unknown asset %s", symbol)
            continue

        # Data completeness caps confidence before anything else is considered.
        confidence = clamp_confidence(item.confidence, asset.confidence_ceiling)

        note: Optional[str] = None
        asset_violations = outcome.violations_for(symbol)
        if asset_violations:
            # A model that misquoted its own evidence has earned less trust in
            # the call built on it, regardless of what it rated itself.
            confidence = downgrade(confidence)
            any_downgrade = True
            note = (
                f"{len(asset_violations)} claim(s) did not match the grounding data; "
                "values were corrected from the context and confidence was lowered."
            )

        recommendations.append(
            AssetRecommendation(
                symbol=symbol,
                recommendation=item.recommendation,
                confidence=confidence,
                confidence_rationale=item.confidence_rationale,
                model_confidence=item.confidence,
                confidence_ceiling=asset.confidence_ceiling,
                ceiling_reason=asset.ceiling_reason,
                supporting_facts=outcome.facts.get(symbol, []),
                risks_or_caveats=item.risks_or_caveats,
                data_completeness=round(asset.completeness.ratio, 4),
                categories_available=asset.completeness.categories_available,
                categories_missing=asset.completeness.categories_missing,
                verification_note=note,
            )
        )

    report.confidence_downgraded = any_downgrade

    return RecommendationResponse(
        status="ok",
        generated_at=context.generated_at,
        quote_currency=context.quote_currency,
        summary=payload.summary,
        recommendations=recommendations,
        # Attached here, from a constant. The model is never asked for it and
        # never able to omit it.
        disclaimer=DISCLAIMER,
        groundedness=report,
        context=context,
        sources=context.sources,
    )


def context_debug(context: RecommendationContext) -> Dict[str, Any]:
    """Plain-data view of a context, used by tests and the log."""
    return to_dict(context)
