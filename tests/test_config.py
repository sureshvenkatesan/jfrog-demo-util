"""Tests for config loader (no external I/O with real files)."""

import pytest

from poc_util.config import (
    get_jfrog_token,
    get_platform_token,
    load_config,
    validate_config,
)


def test_validate_config_requires_jfrog():
    with pytest.raises(ValueError, match="jfrog"):
        validate_config({})


def test_validate_config_requires_base_url():
    with pytest.raises(ValueError, match="base_url"):
        validate_config({"jfrog": {}})


def test_validate_config_requires_token():
    with pytest.raises(ValueError, match="token"):
        validate_config({"jfrog": {"base_url": "https://x.io"}})


def test_validate_config_accepts_access_token():
    validate_config({"jfrog": {"base_url": "https://x.io", "access_token": "t"}})


def test_validate_config_sync_requires_source_patterns():
    with pytest.raises(ValueError, match="source_patterns"):
        validate_config(
            {
                "jfrog": {"base_url": "https://x.io", "token": "t"},
                "sync": {
                    "source_server_id": "a",
                    "target_server_id": "b",
                    "target_repo": "r",
                },
            }
        )
    with pytest.raises(ValueError, match="source_patterns must be an array"):
        validate_config(
            {
                "jfrog": {"base_url": "https://x.io", "token": "t"},
                "sync": {
                    "source_server_id": "a",
                    "source_patterns": "repo:*.whl",
                    "target_server_id": "b",
                    "target_repo": "r",
                },
            }
        )
    with pytest.raises(ValueError, match="source_patterns must not be empty"):
        validate_config(
            {
                "jfrog": {"base_url": "https://x.io", "token": "t"},
                "sync": {
                    "source_server_id": "a",
                    "source_patterns": [],
                    "target_server_id": "b",
                    "target_repo": "r",
                },
            }
        )


def test_validate_config_sync_scan_requires_components():
    """sync-scan.components must be a non-empty array when sync-scan is present."""
    base = {"jfrog": {"base_url": "https://x.io", "token": "t"}}
    with pytest.raises(ValueError, match="sync-scan must be an object"):
        validate_config({**base, "sync-scan": "not-a-dict"})
    with pytest.raises(ValueError, match="non-empty array"):
        validate_config({**base, "sync-scan": {"server_id": "srv"}})
    with pytest.raises(ValueError, match="non-empty array"):
        validate_config({**base, "sync-scan": {"server_id": "srv", "components": []}})
    with pytest.raises(ValueError, match="non-empty array"):
        validate_config(
            {**base, "sync-scan": {"server_id": "srv", "components": "npm://pkg:1"}}
        )
    validate_config(
        {
            **base,
            "sync-scan": {"server_id": "srv", "components": ["npm://pkg:1.0"]},
        }
    )


def test_get_jfrog_token_prefers_token():
    assert get_jfrog_token({"jfrog": {"token": "a", "access_token": "b"}}) == "a"


def test_get_jfrog_token_falls_back_to_access_token():
    assert get_jfrog_token({"jfrog": {"access_token": "b"}}) == "b"


def test_get_platform_token_defaults_to_jfrog_token():
    assert get_platform_token({"jfrog": {"token": "t"}}) == "t"


def test_get_platform_token_uses_platform_token_when_set():
    assert get_platform_token({"jfrog": {"token": "t", "platform_token": "p"}}) == "p"


def test_load_config_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_config_success(tmp_path, sample_config):
    import yaml

    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(sample_config))
    loaded = load_config(path)
    assert loaded["jfrog"]["base_url"] == "https://example.jfrog.io"
    assert loaded["sync"]["source_patterns"] == ["repo:path/*.whl"]
