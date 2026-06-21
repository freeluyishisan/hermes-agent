"""Unit tests for the Mistral provider profile.

Mistral is a plain OpenAI-compatible provider: chat and tool calling ride the
default ``openai_chat`` transport. These tests pin the profile's identity,
endpoint, aliases, auxiliary model, and curated fallback catalog so the
first-class wiring stays intact.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def mistral_profile():
    """Resolve the registered Mistral profile through the public registry."""
    # Importing ``model_tools`` triggers plugin discovery, which registers the
    # Mistral profile in the global provider registry.
    import model_tools  # noqa: F401
    import providers

    profile = providers.get_provider_profile("mistral")
    assert profile is not None, "mistral provider profile must be registered"
    return profile


class TestMistralProfileMetadata:
    """Identity, endpoint, and aux model are wired as a first-class provider."""

    def test_identity_and_endpoint(self, mistral_profile):
        assert mistral_profile.name == "mistral"
        assert mistral_profile.base_url == "https://api.mistral.ai/v1"
        assert mistral_profile.auth_type == "api_key"
        assert "MISTRAL_API_KEY" in mistral_profile.env_vars
        assert mistral_profile.display_name == "Mistral AI"

    def test_aliases_resolve(self):
        import model_tools  # noqa: F401
        import providers

        assert providers.get_provider_profile("mistral-ai").name == "mistral"
        assert providers.get_provider_profile("mistralai").name == "mistral"

    def test_default_aux_model(self, mistral_profile):
        assert mistral_profile.default_aux_model == "mistral-small-latest"

    def test_consumer_api_returns_aux_model(self):
        from agent.auxiliary_client import _get_aux_model_for_provider

        assert _get_aux_model_for_provider("mistral") == "mistral-small-latest"

    def test_fallback_catalog_is_latest_aliases(self, mistral_profile):
        models = mistral_profile.fallback_models
        assert "mistral-large-latest" in models
        assert "codestral-latest" in models
        # Curated fallbacks use stable -latest aliases so they don't go stale.
        assert all(m.endswith("-latest") for m in models)

    def test_no_reasoning_kwargs_emitted(self, mistral_profile):
        """The plain profile sends no provider-specific reasoning kwargs."""
        extra_body, top_level = mistral_profile.build_api_kwargs_extras(
            reasoning_config={"enabled": True, "effort": "high"},
            model="mistral-small-latest",
        )
        assert extra_body == {}
        assert top_level == {}
