"""Model allowlist and routing: the BA gateway (default) and IBM ICA, both through litellm."""

from __future__ import annotations

import os
from dataclasses import dataclass

ICA_BASE = "https://api.servicesessentials.ibm.com/v1/chat-models"


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str
    provider: str          # "gateway" | "ibm-ica"
    strict: bool = False   # premium model: own tight per-IP and global hourly budget (api/main.py)


GATEWAY_DEFAULT = ModelInfo("openai/mistral-large-4-openrouter", "Mistral Large 4", "gateway")
ICA_MODELS = [
    ModelInfo("openai/ibm/granite-4-h-small", "IBM Granite 4 H Small", "ibm-ica"),
    ModelInfo("openai/watsonx/mistralai/mistral-medium-2505", "Mistral Medium (watsonx)", "ibm-ica"),
    ModelInfo("openai/meta-llama/llama-3-3-70b-instruct", "Llama 3.3 70B", "ibm-ica"),
    ModelInfo("openai/claude-haiku-5-5", "Claude Haiku 5.5", "ibm-ica", strict=True),
    ModelInfo("openai/gpt-6-luna", "GPT-6 Luna", "ibm-ica", strict=True),
]


def allowed_models() -> list[ModelInfo]:
    """Default model first (RAI_MODEL, usually the gateway one), then the ICA models."""
    default = os.environ.get("RAI_MODEL") or GATEWAY_DEFAULT.id
    known = [GATEWAY_DEFAULT, *ICA_MODELS]
    first = next((m for m in known if m.id == default), ModelInfo(default, default.split("/", 1)[-1], "gateway"))
    return [first, *(m for m in known if m.id != first.id)]


def route(model: str) -> dict:
    """litellm api_base/api_key for a model id."""
    if any(m.id == model for m in ICA_MODELS):
        return {"api_base": ICA_BASE, "api_key": os.environ.get("ICA_API_KEY")}
    return {"api_base": os.environ.get("LITELLM_BASE_URL"), "api_key": os.environ.get("LITELLM_API_KEY")}
