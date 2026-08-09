"""
Append-only log of every recommendation the app has served.

One JSON object per line: the grounding context that went in, the model output
that came back, and the result of the groundedness check. Deliberately boring
storage -- a file, not a database -- because the point is to have the record at
all.

The reason it exists is calibration. A confidence rating is only worth
something if "high" turns out to be right more often than "low", and that can
only be measured after the fact, by comparing the direction called here against
what the price actually did. The ``price_at_call`` field on each entry is what
makes that comparison possible later; without it the stated confidence can only
ever be assessed on whether it sounds plausible.

Logging never fails a request: a write error is logged and swallowed.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import recommendation_log_path
from ..schemas import to_dict
from ..schemas.grounding import RecommendationContext
from ..schemas.recommendation import GroundednessReport, RecommendationResponse

# Appends happen from an async request handler; the lock keeps two concurrent
# requests from interleaving partial lines.
_write_lock = threading.Lock()


def _price_at_call(context: RecommendationContext, symbol: str) -> Optional[float]:
    metric = context.metric_index().get(f"{symbol}.price")
    return metric.value if metric and metric.is_available else None


def build_entry(
    context: RecommendationContext,
    response: RecommendationResponse,
    model_payload: Optional[Dict[str, Any]],
    groundedness: GroundednessReport,
    model_name: str,
) -> Dict[str, Any]:
    """Assemble the log record. Split out so tests can assert on it directly."""
    calls: List[Dict[str, Any]] = []
    for recommendation in response.recommendations:
        calls.append(
            {
                "symbol": recommendation.symbol,
                "recommendation": recommendation.recommendation,
                "confidence": recommendation.confidence,
                "model_confidence": recommendation.model_confidence,
                "confidence_ceiling": recommendation.confidence_ceiling,
                "data_completeness": recommendation.data_completeness,
                "categories_available": recommendation.categories_available,
                "categories_missing": recommendation.categories_missing,
                # Kept so a later pass can compare the call against what the
                # price actually did.
                "price_at_call": _price_at_call(context, recommendation.symbol),
                "supporting_facts": [
                    to_dict(fact) for fact in recommendation.supporting_facts
                ],
            }
        )

    return {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "generated_at": response.generated_at,
        "model": model_name,
        "quote_currency": response.quote_currency,
        "sources": response.sources,
        "grounding_context": to_dict(context),
        "model_output": model_payload,
        "groundedness": to_dict(groundedness),
        "calls": calls,
    }


def record(
    context: RecommendationContext,
    response: RecommendationResponse,
    model_payload: Optional[Dict[str, Any]],
    groundedness: GroundednessReport,
    model_name: str,
    path: Optional[Path] = None,
) -> None:
    """Append one entry. Never raises."""
    target = path or recommendation_log_path()
    entry = build_entry(context, response, model_payload, groundedness, model_name)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, default=str)
        with _write_lock:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception as error:  # noqa: BLE001 - logging must not break a response
        logging.warning("Could not write recommendation log: %s", error)
