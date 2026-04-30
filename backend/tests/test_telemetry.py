"""
Tests for backend/app/telemetry.py.

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

        # Reload the module so the function runs fresh without cached state.
        import importlib

        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        # Patch the azure.monitor.opentelemetry namespace so an accidental import
        # would be detectable — if it's called the mock records the call.
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
    """When env var is set, configure_azure_monitor() must be called."""

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

        # Should not raise — the function catches and logs the exception.
        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": fake_azure_module}):
            telemetry_module.configure_telemetry()  # no exception expected


class TestConfigureTelemetryFastAPIInstrumentation:
    """Regression tests: FastAPIInstrumentor.instrument_app() must be called.

    Issue #245: configure_azure_monitor was called without FastAPI
    instrumentation, so no request/exception/dependency spans were emitted.
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
        so that request spans are emitted and cloud_RoleName is populated.
        """
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", self._FAKE_CS)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "siege-api")

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
        monkeypatch.setenv("OTEL_SERVICE_NAME", "siege-api")

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

    def test_instrument_app_not_called_when_app_is_none(self, monkeypatch):
        """FastAPIInstrumentor.instrument_app() is NOT called when app argument is None.

        When configure_telemetry() is called without a FastAPI app (or with
        app=None), the function must call configure_azure_monitor() but must
        skip FastAPIInstrumentor().instrument_app() to avoid passing None to
        the instrumentor. This pins the branch so a future refactor cannot
        silently start instrumenting a None app.
        """
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", self._FAKE_CS)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "siege-api")

        import importlib

        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

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
                "opentelemetry.instrumentation.fastapi": fake_fastapi_instrumentor_module,
            },
        ):
            telemetry_module.configure_telemetry(app=None)

        mock_configure.assert_called_once()
        mock_instrumentor.instrument_app.assert_not_called()


class TestConfigureTelemetrySQLAlchemyInstrumentation:
    """SQLAlchemyInstrumentor must be called when engine is provided.

    Issue #257: DB dependencies were invisible in App Insights because
    SQLAlchemy spans were never emitted.  The fix wires
    SQLAlchemyInstrumentor to the async engine's underlying sync_engine
    so that every SQL statement appears as a ``dependency`` span.
    """

    _FAKE_CS = (
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
        "IngestionEndpoint=https://eastus-1.in.applicationinsights.azure.com/;"
        "LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/"
    )

    def test_sqlalchemy_instrument_called_with_sync_engine(self, monkeypatch):
        """SQLAlchemyInstrumentor().instrument(engine=...) is called with
        the engine's sync_engine when an engine is provided.

        The SQLAlchemy OTel instrumentor only accepts a synchronous Engine
        object.  Async engines expose their underlying sync engine via the
        ``.sync_engine`` attribute — that is what must be passed.
        """
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", self._FAKE_CS)

        import importlib

        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_configure = MagicMock()
        mock_sqlalchemy_instrumentor = MagicMock()
        mock_sqlalchemy_instrumentor_cls = MagicMock(return_value=mock_sqlalchemy_instrumentor)

        fake_azure_module = MagicMock()
        fake_azure_module.configure_azure_monitor = mock_configure
        fake_sqlalchemy_module = MagicMock()
        fake_sqlalchemy_module.SQLAlchemyInstrumentor = mock_sqlalchemy_instrumentor_cls

        # Simulate an async engine whose .sync_engine is a sentinel object.
        fake_sync_engine = MagicMock(name="sync_engine")
        fake_engine = MagicMock(name="async_engine")
        fake_engine.sync_engine = fake_sync_engine

        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": fake_azure_module,
                "opentelemetry.instrumentation.sqlalchemy": fake_sqlalchemy_module,
                "opentelemetry.instrumentation.asyncpg": MagicMock(AsyncPGInstrumentor=MagicMock()),
            },
        ):
            telemetry_module.configure_telemetry(engine=fake_engine)

        mock_sqlalchemy_instrumentor.instrument.assert_called_once_with(engine=fake_sync_engine)

    def test_sqlalchemy_instrument_not_called_when_engine_is_none(self, monkeypatch):
        """SQLAlchemyInstrumentor().instrument() is NOT called when no
        engine argument is supplied.

        When configure_telemetry() is called without an engine (e.g. from
        the test suite or a non-DB process), the function must skip
        SQLAlchemy instrumentation rather than raising AttributeError on
        a None engine.
        """
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", self._FAKE_CS)

        import importlib

        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_configure = MagicMock()
        mock_sqlalchemy_instrumentor = MagicMock()
        mock_sqlalchemy_instrumentor_cls = MagicMock(return_value=mock_sqlalchemy_instrumentor)

        fake_azure_module = MagicMock()
        fake_azure_module.configure_azure_monitor = mock_configure
        fake_sqlalchemy_module = MagicMock()
        fake_sqlalchemy_module.SQLAlchemyInstrumentor = mock_sqlalchemy_instrumentor_cls

        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": fake_azure_module,
                "opentelemetry.instrumentation.sqlalchemy": fake_sqlalchemy_module,
                "opentelemetry.instrumentation.asyncpg": MagicMock(AsyncPGInstrumentor=MagicMock()),
            },
        ):
            telemetry_module.configure_telemetry(engine=None)

        mock_sqlalchemy_instrumentor.instrument.assert_not_called()

    def test_sqlalchemy_instrument_not_called_when_telemetry_unconfigured(self, monkeypatch):
        """SQLAlchemyInstrumentor().instrument() is NOT called when
        APPLICATIONINSIGHTS_CONNECTION_STRING is absent.

        If telemetry is disabled (no connection string), neither the Azure
        Monitor nor any instrumentors should be called, even if an engine
        is passed.
        """
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

        import importlib

        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_sqlalchemy_instrumentor = MagicMock()
        mock_sqlalchemy_instrumentor_cls = MagicMock(return_value=mock_sqlalchemy_instrumentor)
        fake_sqlalchemy_module = MagicMock()
        fake_sqlalchemy_module.SQLAlchemyInstrumentor = mock_sqlalchemy_instrumentor_cls

        fake_sync_engine = MagicMock(name="sync_engine")
        fake_engine = MagicMock(name="async_engine")
        fake_engine.sync_engine = fake_sync_engine

        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": MagicMock(),
                "opentelemetry.instrumentation.sqlalchemy": fake_sqlalchemy_module,
                "opentelemetry.instrumentation.asyncpg": MagicMock(AsyncPGInstrumentor=MagicMock()),
            },
        ):
            telemetry_module.configure_telemetry(engine=fake_engine)

        mock_sqlalchemy_instrumentor.instrument.assert_not_called()


class TestConfigureTelemetryAsyncPGInstrumentation:
    """AsyncPGInstrumentor must be called whenever telemetry is active.

    Issue #257: asyncpg spans were absent because AsyncPGInstrumentor was
    never initialised.  Unlike the SQLAlchemy instrumentor, it needs no
    engine argument — it hooks asyncpg at the library level globally.
    """

    _FAKE_CS = (
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
        "IngestionEndpoint=https://eastus-1.in.applicationinsights.azure.com/;"
        "LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/"
    )

    def test_asyncpg_instrument_called_when_telemetry_configured(self, monkeypatch):
        """AsyncPGInstrumentor().instrument() is called when telemetry is
        active, regardless of whether an engine is provided.

        asyncpg is hooked globally — no engine argument is required or
        accepted.
        """
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", self._FAKE_CS)

        import importlib

        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_configure = MagicMock()
        mock_asyncpg_instrumentor = MagicMock()
        mock_asyncpg_instrumentor_cls = MagicMock(return_value=mock_asyncpg_instrumentor)

        fake_azure_module = MagicMock()
        fake_azure_module.configure_azure_monitor = mock_configure
        fake_asyncpg_module = MagicMock()
        fake_asyncpg_module.AsyncPGInstrumentor = mock_asyncpg_instrumentor_cls

        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": fake_azure_module,
                "opentelemetry.instrumentation.sqlalchemy": MagicMock(
                    SQLAlchemyInstrumentor=MagicMock()
                ),
                "opentelemetry.instrumentation.asyncpg": fake_asyncpg_module,
            },
        ):
            telemetry_module.configure_telemetry()

        mock_asyncpg_instrumentor.instrument.assert_called_once_with()

    def test_asyncpg_instrument_not_called_when_telemetry_unconfigured(self, monkeypatch):
        """AsyncPGInstrumentor().instrument() is NOT called when
        APPLICATIONINSIGHTS_CONNECTION_STRING is absent.

        No telemetry initialisation of any kind should occur when the
        connection string is missing.
        """
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

        import importlib

        import app.telemetry as telemetry_module

        importlib.reload(telemetry_module)

        mock_asyncpg_instrumentor = MagicMock()
        mock_asyncpg_instrumentor_cls = MagicMock(return_value=mock_asyncpg_instrumentor)
        fake_asyncpg_module = MagicMock()
        fake_asyncpg_module.AsyncPGInstrumentor = mock_asyncpg_instrumentor_cls

        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.opentelemetry": MagicMock(),
                "opentelemetry.instrumentation.sqlalchemy": MagicMock(
                    SQLAlchemyInstrumentor=MagicMock()
                ),
                "opentelemetry.instrumentation.asyncpg": fake_asyncpg_module,
            },
        ):
            telemetry_module.configure_telemetry()

        mock_asyncpg_instrumentor.instrument.assert_not_called()
