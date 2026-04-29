"""
Tests for bot/app/telemetry.py.

Verifies:
- configure_telemetry() is a no-op when APPLICATIONINSIGHTS_CONNECTION_STRING is unset
- configure_telemetry() calls configure_azure_monitor() when the env var is set
- An unexpected exception from configure_azure_monitor() is swallowed (no crash)
- When both APPLICATIONINSIGHTS_CONNECTION_STRING and OTEL_SERVICE_NAME are set,
  configure_azure_monitor() and FastAPIInstrumentor.instrument_app() are both called
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI


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
            {"azure.monitor.opentelemetry": MagicMock(configure_azure_monitor=mock_configure)},
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
            {"azure.monitor.opentelemetry": MagicMock(configure_azure_monitor=mock_configure)},
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
            {"azure.monitor.opentelemetry": MagicMock(configure_azure_monitor=mock_configure)},
        ):
            telemetry_module.configure_telemetry()

        mock_configure.assert_not_called()


class TestConfigureTelemetryActive:
    """When APPLICATIONINSIGHTS_CONNECTION_STRING is set, configure_azure_monitor() is called."""

    # Fake connection string — intentionally invalid; the SDK accepts any
    # syntactically-valid string at configure time and only fails on export.
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

        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": fake_azure_module}):
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
        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": fake_azure_module}):
            telemetry_module.configure_telemetry()  # no exception expected


class TestConfigureTelemetryFastAPIInstrumentation:
    """Regression tests: FastAPIInstrumentor.instrument_app() must be called.

    Issue #245: the bot HTTP sidecar app was not instrumented, so its
    requests were not emitted to App Insights.
    """

    _FAKE_CS = (
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
        "IngestionEndpoint=https://eastus-1.in.applicationinsights.azure.com/;"
        "LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/"
    )

    def test_instrument_app_called_when_connection_string_and_service_name_set(self, monkeypatch):
        """FastAPIInstrumentor.instrument_app() is called with the FastAPI app.

        When both APPLICATIONINSIGHTS_CONNECTION_STRING and OTEL_SERVICE_NAME
        are present, configure_telemetry(app) must call both
        configure_azure_monitor() and FastAPIInstrumentor.instrument_app(app)
        so that bot HTTP-sidecar request spans are emitted.
        """
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", self._FAKE_CS)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "siege-bot")

        import importlib

        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        fastapi_app = FastAPI()
        mock_configure = MagicMock()
        mock_instrumentor = MagicMock()
        mock_instrumentor_cls = MagicMock(return_value=mock_instrumentor)

        fake_azure_module = MagicMock()
        fake_azure_module.configure_azure_monitor = mock_configure
        fake_fastapi_instrumentor_module = MagicMock()
        fake_fastapi_instrumentor_module.FastAPIInstrumentor = mock_instrumentor_cls

        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": fake_azure_module,
                "opentelemetry.instrumentation.fastapi": (fake_fastapi_instrumentor_module),
            },
        ):
            telemetry_module.configure_telemetry(fastapi_app)

        mock_configure.assert_called_once()
        mock_instrumentor.instrument_app.assert_called_once_with(fastapi_app)

    def test_configure_azure_monitor_called_when_both_env_vars_set(self, monkeypatch):
        """configure_azure_monitor() is called when both env vars are present.

        Regression for issue #245: OTEL_SERVICE_NAME is set in Bicep so the
        distro picks it up automatically — no explicit kwarg needed.
        """
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", self._FAKE_CS)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "siege-bot")

        import importlib

        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        fastapi_app = FastAPI()
        mock_configure = MagicMock()
        mock_instrumentor = MagicMock()
        mock_instrumentor_cls = MagicMock(return_value=mock_instrumentor)

        fake_azure_module = MagicMock()
        fake_azure_module.configure_azure_monitor = mock_configure
        fake_fastapi_instrumentor_module = MagicMock()
        fake_fastapi_instrumentor_module.FastAPIInstrumentor = mock_instrumentor_cls

        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": fake_azure_module,
                "opentelemetry.instrumentation.fastapi": (fake_fastapi_instrumentor_module),
            },
        ):
            telemetry_module.configure_telemetry(fastapi_app)

        mock_configure.assert_called_once_with(logger_name="app")
