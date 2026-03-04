"""Pytest fixtures and shared test data."""

import pytest


@pytest.fixture
def sample_config():
    """Minimal valid config for init and sync."""
    return {
        "jfrog": {
            "base_url": "https://example.jfrog.io",
            "token": "test-token",
        },
        "init": {
            "worker": {"key": "sbom-service"},
            "webhook": {"name": "scanCompleted", "url": "http://worker/execute/sbom-service"},
            "policy": {"name": "sbom-policy", "type": "security"},
            "watch": {
                "name": "poc-watch",
                "assigned_policies": [{"name": "sbom-policy", "type": "security"}],
            },
        },
        "sync": {
            "source_server_id": "source",
            "source_patterns": ["repo:path/*.whl"],
            "target_server_id": "target",
            "target_repo": "target-repo",
            "target_path": "",
        },
    }
