from skye.pricing import (
    DEFAULT_MODEL_PRICE,
    SPARK_SCALE,
    ModelPrice,
    PricingService,
    TurnUsage,
)


def test_provider_cost_is_used_when_present() -> None:
    pricing = PricingService(sparks_per_rub=2.0)
    usage = TurnUsage(model="anything", input_tokens=1_000, output_tokens=1_000)

    # 0.5 ₽ of provider cost at 2 Sparks/₽ = 1 Spark.
    assert pricing.milli(usage, provider_cost_rub=0.5) == 1 * SPARK_SCALE


def test_catalog_is_the_fallback() -> None:
    pricing = PricingService(
        model_prices={"test": ModelPrice(input_per_million=2.0, output_per_million=4.0)}
    )
    usage = TurnUsage(model="test", input_tokens=1_000_000, output_tokens=1_000_000)
    assert pricing.sparks(usage) == 6.0
    assert pricing.milli(usage) == 6 * SPARK_SCALE


def test_unknown_model_uses_default_price() -> None:
    pricing = PricingService()
    usage = TurnUsage(model="mystery", input_tokens=1_000_000)
    assert pricing.sparks(usage) == DEFAULT_MODEL_PRICE.input_per_million


def test_images_add_a_per_image_price() -> None:
    pricing = PricingService(image_prices={"gpt-image-2": 40.0})
    usage = TurnUsage(images=2, image_model="gpt-image-2")
    assert pricing.sparks(usage) == 80.0


def test_any_work_costs_at_least_one_milli_spark() -> None:
    pricing = PricingService()
    tiny = TurnUsage(model="deepseek/deepseek-v4.1-flash", input_tokens=1)
    assert pricing.milli(tiny) == 1
    assert pricing.milli(TurnUsage()) == 0


def test_connector_calls_are_priced_flat() -> None:
    pricing = PricingService(connector_price_rub=0.5, sparks_per_rub=2.0)
    usage = TurnUsage(connector_calls=3)
    assert pricing.cost_rub(usage) == 1.5
    assert pricing.sparks(usage) == 3.0
