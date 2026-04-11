"""
Tests for bot/app/telemetry.py.

Verifies:
- configure_telemetry() is a no-op when APPLICATIONINSIGHTS_CONNECTION_STRING is unset
- configure_telemetry() calls configure_azure_monitor() when the env var is set
- An unexpected exception from configure_azure_monitor() is swallowed (no crash)
"""

from unittest.mock import MagicMock, patch

import pytest


class TestConfigureTelemetryNoop:
    """When APPLICATIONINSIGHTS_CONNECTION_STRING is absent, nothing should happen."""

    def test_noop_when_env_var_missing(self, monkeypatch):
        """No exception and configure_azure_monitor is never imported or called."""
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

        import importlib
        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_configure = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": MagicMock(
                    configure_azure_monitor=mock_configure
                )
            },
        ):
            telemetry_module.configure_telemetry()

        mock_configure.assert_not_called()

    def test_noop_when_env_var_empty_string(self, monkeypatch):
        """An explicitly empty string also results in a no-op."""
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")

        import importlib
        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_configure = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": MagicMock(
                    configure_azure_monitor=mock_configure
                )
            },
        ):
            telemetry_module.configure_telemetry()

        mock_configure.assert_not_called()

    def test_noop_when_env_var_whitespace_only(self, monkeypatch):
        """A whitespace-only string is treated the same as empty."""
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "   ")

        import importlib
        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_configure = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": MagicMock(
                    configure_azure_monitor=mock_configure
                )
            },
        ):
            telemetry_module.configure_telemetry()

        mock_configure.assert_not_called()


class TestConfigureTelemetryActive:
    """When APPLICATIONINSIGHTS_CONNECTION_STRING is set, configure_azure_monitor() must be called."""

    _FAKE_CS = (
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
        "IngestionEndpoint=https://eastus-1.in.applicationinsights.azure.com/;"
        "LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/"
    )

    def test_calls_configure_azure_monitor_when_env_var_set(self, monkeypatch):
        """configure_azure_monitor() is called exactly once with logger_name='app'."""
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", self._FAKE_CS)

        import importlib
        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_configure = MagicMock()
        fake_azure_module = MagicMock()
        fake_azure_module.configure_azure_monitor = mock_configure

        with patch.dict(
            "sys.modules", {"azure.monitor.opentelemetry": fake_azure_module}
        ):
            telemetry_module.configure_telemetry()

        mock_configure.assert_called_once_with(logger_name="app")

    def test_sdk_exception_does_not_propagate(self, monkeypatch):
        """If configure_azure_monitor raises, the exception is swallowed."""
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", self._FAKE_CS)

        import importlib
        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_configure = MagicMock(side_effect=RuntimeError("SDK exploded"))
        fake_azure_module = MagicMock()
        fake_azure_module.configure_azure_monitor = mock_configure

        # Should not raise.
        with patch.dict(
            "sys.modules", {"azure.monitor.opentelemetry": fake_azure_module}
        ):
            telemetry_module.configure_telemetry()  # no exception expected
