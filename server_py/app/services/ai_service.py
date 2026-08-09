"""
AI service: turns a grounding context into a validated, structured call.

Three things changed the character of this module compared with a plain
"ask the model for advice" prompt:

* It is handed **finished metrics**, never a raw price series. Nothing here
  asks the model to compute anything.
* It uses **structured outputs** with a JSON schema, and validates the reply
  against a Pydantic model before returning it. Nothing downstream parses
  prose.
* The prompt makes the field list a **closed world**: cite these names or say
  nothing, and treat a gap as a reason to lower confidence rather than a gap to
  write around.

The prompt is necessary but not sufficient -- ``services/groundedness.py``
re-checks every claim after the fact. This module's job is to make compliance
easy and machine-checkable, not to be trusted.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from ..schemas import from_dict
from ..schemas.grounding import CONFIDENCE_RUBRIC, Metric, RecommendationContext
from ..schemas.recommendation import ModelPayload
from .ai_errors import AIUnavailableError

#: Low, but not zero. This is a structured, numeric task where consistency
#: between runs matters far more than variety of phrasing.
TEMPERATURE = 0.25

DEFAULT_MODEL = "gpt-4.1"

SYSTEM_PROMPT = f"""\
You are a cryptocurrency analyst working under strict grounding rules. You are
given a GROUNDING CONTEXT: a closed list of named fields, each with a value or
the marker `unavailable`.

Rules, in order of priority:

1. You may state only what is in the grounding context. Do not use any price,
   indicator, statistic, news item or market fact from your own knowledge, and
   do not estimate, extrapolate or infer a value that is not given.
2. Every supporting fact must name one field exactly as it is written in the
   context (for example `BTC.rsi_14`) and copy that field's value character for
   character. Do not round, reformat, convert units or paraphrase a number.
3. A field marked `unavailable` has no value. Never supply one for it. Its
   absence is evidence about your confidence, not a gap to write around.
4. Missing data lowers confidence. If a signal category is unavailable, say so
   in `confidence_rationale` and rate confidence lower. Never keep a high
   confidence while hedging the wording.
5. If the available fields disagree with one another, that is a low-confidence
   situation. Say which fields conflict.
6. Do not include disclaimers, legal language or advice framing. That is added
   separately and is not your responsibility.

Confidence rubric -- rate yourself against this exactly:

{CONFIDENCE_RUBRIC}

Who you are writing for:

The reader has never traded and does not know what RSI, MACD or a moving
average is. Rules 1-6 bind you exactly as before -- this section governs the
*wording* of what they already allow, and is never licence to soften, hedge or
invent.

7. Write the shortest plain sentence that is true. Use no technical term
   without saying what it means in ordinary words in the same breath. If you
   write "overbought", "oversold", "bullish", "bearish", "support",
   "resistance" or "momentum", a short gloss must follow it in the same
   sentence -- "overbought (buyers have pushed hard and fast)". If a gloss
   would not fit, choose plainer words instead.
8. Never put a field name (`BTC.rsi_14`, `market.fear_greed_classification`)
   inside `summary`, `confidence_rationale`, `interpretation` or
   `risks_or_caveats`. Name the thing in words -- "the 14-day momentum score",
   "the market's overall mood". Field names belong only in the `metric` key,
   where they are the citation.
9. The app already shows the reader a definition of each metric, so
   `interpretation` must not explain what the indicator is. Say what this
   particular value suggests, and do not restate the metric's name back at
   them.
10. In `confidence_rationale`, do not use the phrases "signal category" or
    "data completeness". Say plainly how much of the information you wanted was
    actually there, and whether the pieces pointed the same way. The grouping
    names this prompt uses -- trend, momentum, volatility, sentiment, market
    structure -- are internal vocabulary: describe what they measure instead of
    naming them.
11. Write to the reader as "you" when referring to their holdings. Avoid
    "the subject portfolio" and similar register.

Return one recommendation per asset listed in the context, using the required
schema. `summary` is two or three sentences about the portfolio as a whole,
under the same grounding rules.\
"""

#: Structured-outputs schema. Written by hand rather than generated from the
#: Pydantic model so it satisfies OpenAI's strict mode (every property
#: required, `additionalProperties` false everywhere) and stays readable as the
#: contract it is.
RESPONSE_FORMAT: Dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "portfolio_recommendations",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "recommendations"],
            "properties": {
                "summary": {
                    "type": "string",
                    "description": (
                        "Two or three sentences on the portfolio as a whole, "
                        "grounded in context fields only. Plain English for a "
                        "first-time reader, addressed as 'you'. No field names, "
                        "no unexplained jargon."
                    ),
                },
                "recommendations": {
                    "type": "array",
                    "description": "One entry per asset in the grounding context.",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "symbol",
                            "recommendation",
                            "confidence",
                            "confidence_rationale",
                            "supporting_facts",
                            "risks_or_caveats",
                        ],
                        "properties": {
                            "symbol": {"type": "string"},
                            "recommendation": {
                                "type": "string",
                                "enum": ["buy", "sell", "hold"],
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                            "confidence_rationale": {
                                "type": "string",
                                "description": (
                                    "Why this confidence level, in plain English: how "
                                    "much of the information you wanted was actually "
                                    "available, and whether the pieces pointed the same "
                                    "way. Do not use the phrases 'signal category' or "
                                    "'data completeness', and do not name fields."
                                ),
                            },
                            "supporting_facts": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["metric", "value", "interpretation"],
                                    "properties": {
                                        "metric": {
                                            "type": "string",
                                            "description": (
                                                "Exact field name from the grounding "
                                                "context."
                                            ),
                                        },
                                        "value": {
                                            "type": "string",
                                            "description": (
                                                "That field's value, copied character "
                                                "for character."
                                            ),
                                        },
                                        "interpretation": {
                                            "type": "string",
                                            "description": (
                                                "One plain sentence on what this "
                                                "particular value suggests, for a reader "
                                                "who has never traded. The app supplies "
                                                "the definition of the metric "
                                                "separately, so do not explain what the "
                                                "indicator is or restate its name."
                                            ),
                                        },
                                    },
                                },
                            },
                            "risks_or_caveats": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "What would invalidate this call, including anything "
                                    "missing that would have mattered. One plain "
                                    "sentence each, no field names, understandable "
                                    "without any trading background."
                                ),
                            },
                        },
                    },
                },
            },
        },
    },
}


def render_metric(metric: Metric) -> str:
    """One context line: the citable name, its value, and how to read it."""
    unit = f" {metric.unit}" if metric.unit and metric.is_available else ""
    line = f"  {metric.field} = {metric.rendered()}{unit}"
    if metric.note:
        line += f"   ({metric.note})"
    return line


def render_context(context: RecommendationContext) -> str:
    """
    Render the grounding context as the closed field list the prompt describes.

    Unavailable fields are listed alongside available ones, on purpose: the
    model has to be able to see what is missing in order to react to it.
    """
    lines: List[str] = [
        "GROUNDING CONTEXT",
        f"generated_at = {context.generated_at}",
        f"quote_currency = {context.quote_currency}",
        "",
        "Portfolio and market-wide fields:",
    ]
    lines.extend(render_metric(metric) for metric in context.shared_metrics)

    for asset in context.assets:
        completeness = asset.completeness
        lines.append("")
        lines.append(
            f"Asset {asset.symbol} ({asset.product_id}) -- "
            f"data completeness {completeness.ratio:.0%} "
            f"({completeness.available}/{completeness.total} fields), "
            f"signal categories available: "
            f"{', '.join(completeness.categories_available) or 'none'}; "
            f"missing: {', '.join(completeness.categories_missing) or 'none'}"
        )
        lines.extend(render_metric(metric) for metric in asset.metrics)

    lines.append("")
    lines.append(
        "Sources: "
        + ", ".join(f"{name}={state}" for name, state in sorted(context.sources.items()))
    )
    return "\n".join(lines)


class AIService:
    """
    Generates structured, grounded recommendations from a context object.

    Kept as a singleton because constructing the OpenAI client is not free and
    the service holds no per-request state.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return

        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        #: Overridable because some gateways only accept temperature=1.
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", str(TEMPERATURE)))
        self.enable_ai_recommendations = (
            os.getenv("ENABLE_AI_RECOMMENDATIONS", "true").lower() == "true"
        )

        if not self.api_key or self.api_key == "your_openai_api_key":
            logging.warning("Missing or invalid OPENAI_API_KEY")
            self.client = None
        else:
            try:
                self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
                logging.info(
                    "Successfully initialized OpenAI client (base_url=%s, model=%s)",
                    self.base_url or "default",
                    self.model,
                )
            except Exception as e:
                logging.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None

        self.initialized = True

    async def generate(
        self,
        context: RecommendationContext,
        feedback: Optional[str] = None,
    ) -> ModelPayload:
        """
        Call the model once and return its validated answer.

        Args:
            context: The closed set of fields the model may reference.
            feedback: Correction text from a failed groundedness check. When
                present this is a retry, and the message names exactly which
                citations were wrong.

        Raises:
            AIUnavailableError: The feature is off, unconfigured, the upstream
                call failed, or the reply did not satisfy the schema.
        """
        if not self.enable_ai_recommendations:
            raise AIUnavailableError(
                "AI recommendations are disabled. Enable them in the .env file."
            )

        if not self.client:
            raise AIUnavailableError(
                "AI recommendations are not available. Check your OPENAI_API_KEY "
                "configuration."
            )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{render_context(context)}\n\n"
                    "Produce one recommendation per asset above, citing only the field "
                    "names shown and copying their values exactly. Cite field names in "
                    "the `metric` key only; write every sentence in plain English for a "
                    "reader who has never traded."
                ),
            },
        ]
        if feedback:
            messages.append({"role": "user", "content": feedback})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                response_format=RESPONSE_FORMAT,
                # Plain English is longer than analyst shorthand, and a
                # multi-asset portfolio produces one full card per holding.
                max_tokens=3000,
            )
        except Exception as error:  # noqa: BLE001
            logging.error("OpenAI API error: %s", error)
            raise AIUnavailableError("The analysis service did not respond.") from error

        choice = response.choices[0]
        refusal = getattr(choice.message, "refusal", None)
        if refusal:
            raise AIUnavailableError(f"The model declined to answer: {refusal}")

        content = choice.message.content
        if not content:
            raise AIUnavailableError("The analysis service returned an empty response.")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as error:
            logging.error("Model returned non-JSON content: %s", content[:400])
            raise AIUnavailableError("The analysis service returned an unreadable response.") from error

        try:
            return from_dict(ModelPayload, data)
        except Exception as error:  # noqa: BLE001 - pydantic ValidationError shape varies
            logging.error("Model response failed schema validation: %s", error)
            raise AIUnavailableError(
                "The analysis service returned a response in an unexpected shape."
            ) from error
