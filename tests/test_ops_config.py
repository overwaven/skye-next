from __future__ import annotations

from skye.config import Settings
from skye.ops_config import (
    GROUPS,
    describe_fields,
    validate_values,
)


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "telegram_bot_token": "123:token",
        "openai_api_key": "sk-test",
        "skye_owner_ids": "1, 2",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_every_setting_is_described() -> None:
    specs = describe_fields()
    assert {spec.key for spec in specs} == set(Settings.model_fields)
    assert all(spec.group in GROUPS for spec in specs)
    assert len(specs) == len(Settings.model_fields)


def test_kinds_and_secrets() -> None:
    by_key = {spec.key: spec for spec in describe_fields()}
    assert by_key["skye_sandbox_enabled"].kind == "bool"
    assert by_key["skye_max_turns"].kind == "int"
    assert by_key["skye_owner_ids"].kind == "list"
    assert by_key["skye_default_reasoning"].kind == "select"
    assert by_key["skye_default_reasoning"].choices
    assert by_key["skye_provider_api_key"].secret
    assert by_key["skye_database_path"].read_only
    assert by_key["skye_max_turns"].minimum == 2
    assert by_key["skye_max_turns"].maximum == 100


def test_validate_reports_cross_field_rules() -> None:
    validated, errors = validate_values(settings(), {"skye_max_context_tokens": 1000})
    assert validated is None
    assert "skye_max_context_tokens" in errors
    assert "compaction" in errors["skye_max_context_tokens"].lower()


