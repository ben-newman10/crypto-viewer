"""
Typed contracts for the recommendation pipeline.

``grounding`` describes everything the model is *allowed* to reference;
``recommendation`` describes what it is allowed to return. Both are validated,
so a downstream consumer never has to parse prose.
"""

from typing import Any, Dict, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def to_dict(model: BaseModel) -> Dict[str, Any]:
    """Dump a model to plain data under either Pydantic 1 or 2."""
    dump = getattr(model, "model_dump", None)
    if callable(dump):
        return dump()
    return model.dict()


def from_dict(model_cls: Type[T], data: Dict[str, Any]) -> T:
    """Validate plain data into a model under either Pydantic 1 or 2."""
    validate = getattr(model_cls, "model_validate", None)
    if callable(validate):
        return validate(data)
    return model_cls.parse_obj(data)
