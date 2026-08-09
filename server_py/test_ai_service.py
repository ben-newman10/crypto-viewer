"""
Tests for the AI seam.

Two halves: the fake service that stands in for OpenAI everywhere else in the
suite, and the real service's prompt construction and response handling —
exercised against a stub client so no API key is needed and no request leaves
the process.
"""

import json

import pytest

from app.schemas.grounding import CONFIDENCE_RUBRIC
from app.schemas.recommendation import ModelPayload
from app.services import ai_service as ai_service_module
from app.services.ai_errors import AIUnavailableError
from app.services.ai_service import AIService, RESPONSE_FORMAT, TEMPERATURE, render_context
from app.services.context_builder import ContextBuilder
from app.services.fakes import FakeAIService, FakeCoinbaseService, FakeMarketContextService, Scenario
from app.services.fakes import scenarios


async def context_for(flags=None):
    scenario = Scenario.parse(flags)
    return await ContextBuilder(
        FakeCoinbaseService(scenario), FakeMarketContextService(scenario)
    ).build()


# --- the fake ---------------------------------------------------------------


async def test_the_fake_returns_a_validated_structured_payload_not_prose():
    context = await context_for()
    payload = await FakeAIService().generate(context)

    assert isinstance(payload, ModelPayload)
    assert {item.symbol for item in payload.recommendations} == {"BTC", "ETH", "SOL"}
    for item in payload.recommendations:
        assert item.recommendation in {"buy", "sell", "hold"}
        assert item.confidence in {"low", "medium", "high"}
        assert item.supporting_facts


async def test_the_fake_quotes_values_out_of_the_context_it_was_given():
    context = await context_for()
    payload = await FakeAIService().generate(context)
    index = context.metric_index()

    for item in payload.recommendations:
        for fact in item.supporting_facts:
            assert fact.metric in index
            assert fact.value == index[fact.metric].rendered()


async def test_the_fake_spreads_its_evidence_across_signal_categories():
    context = await context_for()
    payload = await FakeAIService().generate(context)
    index = context.metric_index()

    for item in payload.recommendations:
        categories = {index[fact.metric].category for fact in item.supporting_facts}
        assert len(categories) == len(item.supporting_facts)


async def test_the_ungrounded_scenario_really_is_ungrounded():
    context = await context_for()
    payload = await FakeAIService(Scenario.parse(scenarios.UNGROUNDED_AI)).generate(context)
    index = context.metric_index()

    facts = payload.recommendations[0].supporting_facts
    assert any(fact.metric not in index for fact in facts), "no invented field"
    assert any(
        fact.metric in index and fact.value != index[fact.metric].rendered() for fact in facts
    ), "no fabricated value"


async def test_a_hard_failure_raises_so_the_router_can_answer_with_a_500():
    with pytest.raises(RuntimeError):
        await FakeAIService(Scenario.parse(scenarios.ERROR_AI)).generate(await context_for())


async def test_a_soft_failure_raises_the_unavailable_error():
    with pytest.raises(AIUnavailableError):
        await FakeAIService(Scenario.parse(scenarios.DEGRADED_AI)).generate(await context_for())


# --- prompt construction ----------------------------------------------------


async def test_the_rendered_context_lists_every_citable_field_with_its_value():
    context = await context_for()
    rendered = render_context(context)

    for field, metric in context.metric_index().items():
        assert field in rendered
        assert metric.rendered() in rendered


async def test_unavailable_fields_appear_in_the_prompt_rather_than_being_hidden():
    """
    A gap the model cannot see is a gap it cannot lower its confidence for, so
    unavailable fields must be listed alongside the available ones.
    """
    context = await context_for(scenarios.PARTIAL_DATA)
    rendered = render_context(context)

    assert "BTC.sma_200 = unavailable" in rendered
    assert "market.fear_greed_index = unavailable" in rendered
    # And the reason travels with them.
    assert "needs 200 daily closes" in rendered


async def test_the_prompt_states_the_completeness_the_ceiling_was_derived_from():
    context = await context_for(scenarios.PARTIAL_DATA)
    rendered = render_context(context)
    assert "data completeness 47%" in rendered
    assert "missing: trend, sentiment, market_structure" in rendered


def test_the_system_prompt_carries_the_same_rubric_the_server_enforces():
    assert CONFIDENCE_RUBRIC in ai_service_module.SYSTEM_PROMPT


def test_the_response_schema_is_strict_and_closed():
    """
    OpenAI's structured outputs only guarantee schema conformance in strict
    mode, which requires every property listed as required and no additional
    properties at any level.
    """
    schema = RESPONSE_FORMAT["json_schema"]
    assert schema["strict"] is True

    def assert_closed(node):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for child in node["properties"].values():
                assert_closed(child)
        elif node.get("type") == "array":
            assert_closed(node["items"])

    assert_closed(schema["schema"])


# --- the real service's response handling -----------------------------------


class _StubClient:
    """Minimal stand-in for AsyncOpenAI, capturing the request it was given."""

    def __init__(self, content=None, refusal=None, error=None):
        self.content = content
        self.refusal = refusal
        self.error = error
        self.calls = []
        self.chat = self

    @property
    def completions(self):
        return self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error

        message = type("Message", (), {"content": self.content, "refusal": self.refusal})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


def _service(client):
    """An AIService wired to a stub client, bypassing the singleton's __init__."""
    service = AIService.__new__(AIService)
    service.initialized = True
    service.api_key = "test"
    service.model = "test-model"
    service.temperature = TEMPERATURE
    service.enable_ai_recommendations = True
    service.client = client
    return service


VALID_RESPONSE = json.dumps(
    {
        "summary": "A summary.",
        "recommendations": [
            {
                "symbol": "BTC",
                "recommendation": "hold",
                "confidence": "medium",
                "confidence_rationale": "two categories agree",
                "supporting_facts": [
                    {"metric": "BTC.rsi_14", "value": "62.6289", "interpretation": "neutral"}
                ],
                "risks_or_caveats": ["a sharp move would invalidate this"],
            }
        ],
    }
)


async def test_a_valid_response_is_parsed_into_the_payload_model():
    service = _service(_StubClient(content=VALID_RESPONSE))
    payload = await service.generate(await context_for())

    assert payload.summary == "A summary."
    assert payload.recommendations[0].symbol == "BTC"


async def test_the_call_uses_a_low_temperature_and_the_structured_schema():
    client = _StubClient(content=VALID_RESPONSE)
    await _service(client).generate(await context_for())

    (request,) = client.calls
    # Consistency matters more than variety for a structured, numeric task.
    assert request["temperature"] == pytest.approx(0.25)
    assert request["response_format"] is RESPONSE_FORMAT


async def test_retry_feedback_is_appended_as_an_extra_turn():
    client = _StubClient(content=VALID_RESPONSE)
    await _service(client).generate(await context_for(), feedback="you misquoted BTC.rsi_14")

    messages = client.calls[0]["messages"]
    assert messages[-1]["content"] == "you misquoted BTC.rsi_14"
    assert messages[0]["role"] == "system"


async def test_non_json_content_is_reported_as_unavailable_not_returned():
    service = _service(_StubClient(content="Here are my thoughts on Bitcoin..."))
    with pytest.raises(AIUnavailableError):
        await service.generate(await context_for())


async def test_json_that_does_not_match_the_schema_is_rejected():
    service = _service(_StubClient(content=json.dumps({"summary": "hi", "recommendations": "no"})))
    with pytest.raises(AIUnavailableError):
        await service.generate(await context_for())


async def test_a_refusal_is_reported_rather_than_treated_as_an_answer():
    service = _service(_StubClient(content=None, refusal="I can't help with that"))
    with pytest.raises(AIUnavailableError):
        await service.generate(await context_for())


async def test_an_upstream_error_becomes_an_unavailable_error():
    service = _service(_StubClient(error=RuntimeError("connection reset")))
    with pytest.raises(AIUnavailableError):
        await service.generate(await context_for())


async def test_the_feature_flag_and_a_missing_key_both_short_circuit_the_call():
    disabled = _service(_StubClient(content=VALID_RESPONSE))
    disabled.enable_ai_recommendations = False
    with pytest.raises(AIUnavailableError):
        await disabled.generate(await context_for())

    unconfigured = _service(None)
    with pytest.raises(AIUnavailableError):
        await unconfigured.generate(await context_for())
