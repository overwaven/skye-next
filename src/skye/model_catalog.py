"""Host-controlled picker entries. Prices are read from OpenRouter, never invented."""

import time
from typing import Literal, cast

import httpx
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
    ]
]
IMAGE_MODELS = [
    PickerModel(id="openai/gpt-image-2.6-sunburst", name="GPT Image 2.6 Sunburst", tier="Premium"),
    PickerModel(id="google/gemini-nano-banana-2.1", name="Nano Banana 2.1", tier="Medium"),
]

# Base USD rates checked against OpenRouter on 2026-11-06. Actual usage.cost
# takes precedence; this is only the fallback when streaming omits the cost.
TEXT_USD: dict[str, tuple[float, float, float]] = {
    "openai/gpt-6.1-terra": (1, 5, 0.05),
    "deepseek/deepseek-v4.1-flash-1017": (0.15, 0.6, 0.003),
    "anthropic/claude-haiku-5.5": (0.1, 0.5, 0.01),
    "openai/gpt-6.1-sol": (2, 10, 0.1),
    "anthropic/claude-sonnet-5.5": (2, 10, 0.1),
    "openai/gpt-6-luna": (0.1, 0.5, 0.01),
    "anthropic/claude-opus-5.5": (4, 20, 0.2),
    "x-ai/grok-4.7": (2, 6, 0.5),
}


class PickerPrices:
    def __init__(self) -> None:
        self._prices: dict[str, str] = {}
        self._expires = 0.0

    async def labels(self, models: list[PickerModel], *, images: bool) -> list[str]:
        if time.monotonic() >= self._expires or any(m.id not in self._prices for m in models):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get("https://openrouter.ai/api/v1/models")
                    response.raise_for_status()
                    for item in response.json()["data"]:
                        price = item["pricing"]
                        a, b = float(price["prompt"]), float(price["completion"])
                        self._prices[item["id"]] = f"${a * 1e6:g}/${b * 1e6:g} per 1M in/out"
                    for model in models if images else []:
                        response = await client.get(
                            f"https://openrouter.ai/api/v1/images/models/{model.id}/endpoints"
                        )
                        response.raise_for_status()
                        prices = [
                            float(p["cost_usd"]) * 1e6
                            for endpoint in response.json()["endpoints"]
                            for p in endpoint["pricing"]
                            if p["billable"] == "output_image" and p["unit"] == "token"
                        ]
                        if prices:
                            self._prices[model.id] = f"from ${min(prices):g}/1M image tokens"
                self._expires = time.monotonic() + 300
            except httpx.HTTPError, ValueError, KeyError, TypeError:
                self._expires = time.monotonic() + 15
        return [self._prices.get(model.id, "Price unavailable") for model in models]
