"""Host-controlled picker entries."""

from typing import Literal, cast

from pydantic import BaseModel, Field


class PickerModel(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=60)
    tier: Literal["Lightweight", "Medium", "Premium"]


TEXT_MODELS = [
    PickerModel(id=model, name=name, tier=cast(Literal["Lightweight", "Medium", "Premium"], tier))
    for model, name, tier in [
        ("openai/gpt-6.1-terra", "GPT-6.1 Terra", "Medium"),
        ("deepseek/deepseek-v4.1-flash-1017", "DeepSeek V4.1 Flash 1017", "Lightweight"),
        ("anthropic/claude-haiku-5.5", "Claude Haiku 5.5", "Lightweight"),
        ("openai/gpt-6.1-sol", "GPT-6.1 Sol", "Premium"),
        ("anthropic/claude-sonnet-5.5", "Claude Sonnet 5.5", "Premium"),
        ("openai/gpt-6-luna", "GPT-6 Luna", "Lightweight"),
        ("anthropic/claude-opus-5.5", "Claude Opus 5.5", "Premium"),
        ("x-ai/grok-4.7", "Grok 4.7", "Premium"),
        ("meta/muse-ember", "Muse Ember", "Lightweight"),
    ]
]
IMAGE_MODELS = [
    PickerModel(id="openai/gpt-image-2.6-sunburst", name="GPT Image 2.6 Sunburst", tier="Premium"),
    PickerModel(id="google/gemini-nano-banana-2.1", name="Nano Banana 2.1", tier="Medium"),
]

# Base USD rates checked against OpenRouter. Actual usage.cost takes
# precedence; this is only the fallback when streaming omits the cost.
TEXT_USD: dict[str, tuple[float, float, float]] = {
    "openai/gpt-6.1-terra": (1, 5, 0.05),
    "deepseek/deepseek-v4.1-flash-1017": (0.15, 0.6, 0.003),
    "anthropic/claude-haiku-5.5": (0.1, 0.5, 0.01),
    "openai/gpt-6.1-sol": (2, 10, 0.1),
    "anthropic/claude-sonnet-5.5": (2, 10, 0.1),
    "openai/gpt-6-luna": (0.1, 0.5, 0.01),
    "anthropic/claude-opus-5.5": (4, 20, 0.2),
    "x-ai/grok-4.7": (2, 6, 0.5),
    "meta/muse-ember": (0.1, 0.5, 0.004),
}
