"""
Tests for Phase 1 AI Gateway configuration.
Validates APIM feature flag behavior and endpoint routing.
"""
import os


class TestApimConfig:
    """Tests for APIM configuration loading."""

    def test_apim_disabled_by_default(self):
        """USE_APIM_GATEWAY should default to False."""
        os.environ.pop("USE_APIM_GATEWAY", None)
        from common.config.config import Config

        config = Config()
        assert config.use_apim_gateway is False

    def test_apim_enabled_via_env_var(self):
        """USE_APIM_GATEWAY=true should enable APIM routing."""
        os.environ["USE_APIM_GATEWAY"] = "true"
        os.environ["APIM_ENDPOINT"] = "https://apim-test.azure-api.net"
        os.environ["APIM_SUBSCRIPTION_KEY"] = "test-key-123"

        import importlib
        import common.config.config as config_module

        importlib.reload(config_module)
        config = config_module.Config()

        assert config.use_apim_gateway is True
        assert config.apim_endpoint == "https://apim-test.azure-api.net"
        assert config.apim_subscription_key == "test-key-123"

        os.environ.pop("USE_APIM_GATEWAY", None)
        os.environ.pop("APIM_ENDPOINT", None)
        os.environ.pop("APIM_SUBSCRIPTION_KEY", None)

    def test_apim_false_string_values(self):
        """USE_APIM_GATEWAY with 'false', '0', '' should be disabled."""
        import importlib
        import common.config.config as config_module

        for falsy_value in ["false", "False", "FALSE", "0", ""]:
            os.environ["USE_APIM_GATEWAY"] = falsy_value
            importlib.reload(config_module)
            config = config_module.Config()
            assert config.use_apim_gateway is False, f"Expected False for value: '{falsy_value}'"

        os.environ.pop("USE_APIM_GATEWAY", None)

    def test_apim_endpoint_defaults_empty(self):
        """APIM_ENDPOINT should default to empty string."""
        os.environ.pop("APIM_ENDPOINT", None)
        import importlib
        import common.config.config as config_module

        importlib.reload(config_module)
        config = config_module.Config()
        assert config.apim_endpoint == ""

    def test_apim_api_version_default(self):
        """APIM_API_VERSION should default to 2024-02-01."""
        os.environ.pop("APIM_API_VERSION", None)
        import importlib
        import common.config.config as config_module

        importlib.reload(config_module)
        config = config_module.Config()
        assert config.apim_api_version == "2024-02-01"


class TestApimPolicyFiles:
    """Tests that APIM policy files exist and have correct streaming configuration."""

    def test_chat_policy_exists(self):
        assert os.path.exists("../infra/apim-policies/chat-policy.xml") or \
               os.path.exists("infra/apim-policies/chat-policy.xml") or \
               os.path.exists("../../infra/apim-policies/chat-policy.xml")

    def test_chart_policy_exists(self):
        assert os.path.exists("../infra/apim-policies/chart-policy.xml") or \
               os.path.exists("infra/apim-policies/chart-policy.xml") or \
               os.path.exists("../../infra/apim-policies/chart-policy.xml")

    def test_chat_policy_has_no_buffer(self):
        """Chat policy must NOT buffer request body (required for streaming SSE)."""
        import glob

        files = glob.glob("**/chat-policy.xml", recursive=True)
        assert len(files) > 0, "chat-policy.xml not found"

        with open(files[0], encoding="utf-8") as f:
            content = f.read()

        assert 'buffer-request-body="false"' in content, \
            "Chat policy MUST have buffer-request-body='false' for SSE streaming"

    def test_chart_policy_has_cache(self):
        """Chart policy should have cache-store for cost optimization."""
        import glob

        files = glob.glob("**/chart-policy.xml", recursive=True)
        assert len(files) > 0, "chart-policy.xml not found"

        with open(files[0], encoding="utf-8") as f:
            content = f.read()

        assert "cache-store" in content, \
            "Chart policy should have cache-store for cost optimization"
