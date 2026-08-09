"""Shared failure type for the AI seam, importable by the real and fake services."""


class AIUnavailableError(RuntimeError):
    """
    The model could not produce a usable structured answer.

    Raised for a missing API key, a disabled feature flag, an upstream error,
    or a response that fails schema validation. It is deliberately *not* used
    for thin grounding data: that is a confidence problem, not an outage, and
    the pipeline still returns a recommendation in that case.
    """
