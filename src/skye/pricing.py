"""Provider-agnostic pricing: turn token and image usage into Sparks.

Prices live here as data, keyed by model id, so switching model providers is a
catalog edit rather than a code change. When a provider reports the real cost of
a request (Selectel AI Router returns ``usage.cost`` in rubles), that value wins
and is converted through :attr:`PricingService.sparks_per_rub`; without it we
fall back to this catalog.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SPARK_SCALE = 1000
"""Milli-Sparks per Spark. Balances and prices are stored as integer milli-Sparks."""


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Retail Sparks per one million tokens."""

    input_per_million: float
    output_per_million: float
    cached_input_per_million: float = 0.0


@dataclass(frozen=True, slots=True)
class TurnUsage:
    """Everything a single run costs, before it is turned into Sparks."""

    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    images: int = 0
    image_model: str | None = None
    provider_cost_rub: float | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# A deliberately small default catalog. Operators tune these against the
# provider's live prices; unknown models fall back to DEFAULT_MODEL_PRICE.
DEFAULT_MODEL_PRICE = ModelPrice(
    input_per_million=1.0,
    output_per_million=3.0,
    cached_input_per_million=0.25,
)

MODEL_PRICES: dict[str, ModelPrice] = {
    "gpt-5.6-luna": ModelPrice(
        input_per_million=1.0, output_per_million=4.0, cached_input_per_million=0.25
    ),
    "deepseek/deepseek-v4.1-flash": ModelPrice(
        input_per_million=0.3, output_per_million=1.2, cached_input_per_million=0.06
    ),
}

DEFAULT_IMAGE_PRICE = 30.0

IMAGE_PRICES: dict[str, float] = {
    "gpt-image-2": 40.0,
    "gpt-image-2.5": 40.0,
    "openai/gpt-image-2.5/flare/text-to-image": 40.0,
    "openai/gpt-image-2.5/flare/edit": 40.0,
    "microsoft/mai-image-2.6": 25.0,
    "recraft-v4.1-flash": 15.0,
}


class PricingService:
    def __init__(
        self,
        *,
        sparks_per_rub: float = 1.0,
        model_prices: dict[str, ModelPrice] | None = None,
        image_prices: dict[str, float] | None = None,
    ) -> None:
        if sparks_per_rub <= 0:
            raise ValueError("sparks_per_rub must be positive")
        self.sparks_per_rub = sparks_per_rub
        self.model_prices = dict(MODEL_PRICES if model_prices is None else model_prices)
        self.image_prices = dict(IMAGE_PRICES if image_prices is None else image_prices)

    def model_price(self, model: str | None) -> ModelPrice:
        if model is not None and model in self.model_prices:
            return self.model_prices[model]
        return DEFAULT_MODEL_PRICE

    def image_price(self, model: str | None) -> float:
        if model is not None and model in self.image_prices:
            return self.image_prices[model]
        return DEFAULT_IMAGE_PRICE

    def sparks(self, usage: TurnUsage, *, provider_cost_rub: float | None = None) -> float:
        """Retail Sparks for one run, before rounding to milli-Sparks.

        A provider-reported cost, when present, is the source of truth; the
        catalog is only the fallback.
        """
        if provider_cost_rub is not None and provider_cost_rub > 0:
            return provider_cost_rub * self.sparks_per_rub
        price = self.model_price(usage.model)
        total = (
            usage.input_tokens / 1_000_000 * price.input_per_million
            + usage.output_tokens / 1_000_000 * price.output_per_million
            + usage.cached_tokens / 1_000_000 * price.cached_input_per_million
        )
        total += usage.images * self.image_price(usage.image_model)
        return max(total, 0.0)

    def milli(self, usage: TurnUsage, *, provider_cost_rub: float | None = None) -> int:
        """Sparks charged for a run, in integer milli-Sparks.

        Any non-zero usage costs at least one milli-Spark so a run is never
        silently free when it did work.
        """
        sparks = self.sparks(usage, provider_cost_rub=provider_cost_rub)
        if sparks <= 0:
            return 0
        return max(1, math.ceil(sparks * SPARK_SCALE))
