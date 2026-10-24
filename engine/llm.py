"""Thin LiteLLM wrapper: JSON-mode completion validated against a pydantic model."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from engine.models import route

T = TypeVar("T", bound=BaseModel)


class LLMFormatError(Exception):
    pass


def load_env(path: str | Path = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def default_model() -> str:
    load_env()
    return os.environ.get("RAI_MODEL", "openai/gemma-4-31b-it-openrouter")


def _raw(messages: list[dict], model: str, json_mode: bool = True) -> str:
    import litellm

    load_env()
    kwargs = dict(
        model=model,
        messages=messages,
        **route(model),
        temperature=0,
        max_tokens=8000,   # reasoning models spend tokens before the JSON; a low cap yields empty content
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = litellm.completion(**kwargs)
    return resp.choices[0].message.content or ""


def complete_text(messages: list[dict], model: str) -> str:
    return _raw(messages, model, json_mode=False).strip()


def _extract_json(text: str) -> object:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def complete_json(messages: list[dict], model: str, schema: type[T]) -> T:
    """One call plus four retries (reasoning models occasionally return empty/truncated JSON); raises LLMFormatError if the output never validates."""
    last: Exception | None = None
    for _ in range(5):
        try:
            return schema.model_validate(_extract_json(_raw(messages, model)))
        except (json.JSONDecodeError, ValidationError) as e:
            last = e
    raise LLMFormatError(str(last))
