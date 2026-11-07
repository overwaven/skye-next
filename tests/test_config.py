from pathlib import Path

import pytest
from pydantic import ValidationError

from skye.config import Settings


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "telegram_bot_token": "123:token",
        "openai_api_key": "sk-test",
        "openrouter_api_key": None,
        "skye_owner_ids": "1, 2",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_owner_is_required() -> None:
    with pytest.raises(ValidationError):
        settings(skye_owner_ids="")


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ('"ck_live_abc"', "ck_live_abc"),
        ("'ck_live_abc'", "ck_live_abc"),
        ("Bearer ck_live_abc", "ck_live_abc"),
        ("x-api-key: ck_live_abc", "ck_live_abc"),
        ("  ck_live_abc  ", "ck_live_abc"),
    ],
)
def test_composio_key_strips_wrapping(raw: str, cleaned: str) -> None:
    assert settings(composio_api_key=raw).composio_api_key == cleaned


def test_openrouter_key_selects_openrouter_base_url_and_namespaced_models() -> None:
    loaded = settings(
        openai_api_key=None,
        openrouter_api_key="sk-or-test",
        skye_default_model="anthropic/claude-sonnet-4.6",
        skye_transcription_model="openai/whisper-large-v3",
        skye_speech_model="openai/gpt-4o-mini-tts",
        skye_image_model="openai/gpt-5-image",
    )

    assert loaded.provider_api_key == "sk-or-test"
    assert loaded.provider_base_url == "https://openrouter.ai/api/v1"


def test_unified_provider_key_wins_over_legacy_keys() -> None:
    loaded = settings(
        openai_api_key="sk-legacy",
        openrouter_api_key="sk-or-legacy",
        skye_provider_api_key="sk-unified",
        skye_provider_base_url="https://llm.example.com/v1",
    )

    assert loaded.provider_api_key == "sk-unified"
    assert loaded.provider_base_url == "https://llm.example.com/v1"


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ("https://openrouter.ai/api/v1/chat/completions", "https://openrouter.ai/api/v1"),
        ("https://openrouter.ai/api/v1/chat/completions/", "https://openrouter.ai/api/v1"),
        ("https://openrouter.ai/api/v1/responses", "https://openrouter.ai/api/v1"),
        ("https://llm.example.com/v1", "https://llm.example.com/v1"),
    ],
)
def test_base_url_keeps_only_the_api_root(raw: str, cleaned: str) -> None:
    loaded = settings(skye_provider_base_url=raw)

    assert loaded.provider_base_url == cleaned
    assert loaded.image_base_url == cleaned
    assert loaded.audio_base_url == cleaned


def test_media_endpoints_fall_back_to_chat_provider() -> None:
    loaded = settings(
        skye_provider_api_key="sk-unified",
        skye_provider_base_url="https://llm.example.com/v1",
    )

    assert loaded.image_api_key == "sk-unified"
    assert loaded.image_base_url == "https://llm.example.com/v1"
    assert loaded.audio_api_key == "sk-unified"
    assert loaded.audio_base_url == "https://llm.example.com/v1"
    assert loaded.image_endpoint_overridden is False
    assert loaded.audio_endpoint_overridden is False


def test_media_endpoints_accept_separate_keys_and_urls() -> None:
    loaded = settings(
        skye_image_api_key="sk-img",
        skye_image_base_url="https://img.example.com/v1",
        skye_audio_base_url="https://audio.example.com/v1",
    )

    assert loaded.image_api_key == "sk-img"
    assert loaded.image_base_url == "https://img.example.com/v1"
    assert loaded.audio_api_key == "sk-test"
    assert loaded.audio_base_url == "https://audio.example.com/v1"
    assert loaded.image_endpoint_overridden is True
    assert loaded.audio_endpoint_overridden is True


def test_fal_media_is_selected_per_capability() -> None:
    # Without a key nothing goes to fal.
    plain = settings()
    assert plain.images_on_fal is False
    assert plain.audio_on_fal is False

    # With a key, ``auto`` sends both to fal.
    auto = settings(skye_fal_key="fal-test", skye_image_provider="auto", skye_audio_provider="auto")
    assert auto.images_on_fal is True
    assert auto.audio_on_fal is True

    # Capabilities can be split: images on the chat provider, speech on fal.
    split = settings(
        skye_fal_key="fal-test",
        skye_image_provider="compatible",
        skye_audio_provider="fal",
    )
    assert split.images_on_fal is False
    assert split.audio_on_fal is True


def test_fal_provider_requires_a_key() -> None:
    with pytest.raises(ValidationError):
        settings(skye_image_provider="fal")
    with pytest.raises(ValidationError):
        settings(skye_audio_provider="fal")


def test_context_limit_must_exceed_compaction_threshold() -> None:
    with pytest.raises(ValidationError):
        settings(
            skye_compaction_threshold_tokens=50_000,
            skye_max_context_tokens=50_000,
        )


def test_tpm_budget_must_cover_one_maximum_request() -> None:
    with pytest.raises(ValidationError):
        settings(skye_tpm_budget=53_999)


def test_sandbox_domains_are_parsed_from_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_BOT_TOKEN=123:token\nOPENAI_API_KEY=sk-test\nSKYE_OWNER_IDS=1\n"
        "SKYE_SANDBOX_ALLOWED_DOMAINS=pypi.org, GitHub.com, files.pythonhosted.org\n",
        encoding="utf-8",
    )

    loaded = Settings(_env_file=env_file)  # type: ignore[call-arg]

    assert loaded.skye_sandbox_allowed_domains == (
        "pypi.org",
        "github.com",
        "files.pythonhosted.org",
    )
