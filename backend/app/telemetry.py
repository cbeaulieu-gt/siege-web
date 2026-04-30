"""Application Insights / OpenTelemetry initialisation for the backend.

Call ``configure_telemetry(app, engine)`` once at process start, **after**
``app = FastAPI(...)`` is constructed and the SQLAlchemy async engine is
available.  If ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is not set the
function is a no-op so local development is unaffected.

``OTEL_SERVICE_NAME`` must be set in the environment (via the Bicep
container-app definition for deployed environments) so that
``configure_azure_monitor()`` picks it up automatically and tags every
span with ``service.name``, which Azure Application Insights surfaces as
``cloud_RoleName``.  Without it every span lands under the synthetic
``unknown_service`` node and the Application Map cannot render.
"""

import logging
import os
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


def configure_telemetry(
    app: FastAPI | None = None,
    engine: "AsyncEngine | None" = None,
) -> None:
    """Initialise Azure Monitor OpenTelemetry and instrument the app.

    The ``azure-monitor-opentelemetry`` distro reads
    ``APPLICATIONINSIGHTS_CONNECTION_STRING`` from the environment
    automatically when ``configure_azure_monitor()`` is called without an
    explicit ``connection_string`` argument.  We guard the call so that a
    missing env var is a silent no-op rather than an import-time or startup
    error.

    ``OTEL_SERVICE_NAME`` is read from the environment by the OpenTelemetry
    SDK automatically — set it to ``siege-api`` in the container environment
    so that ``cloud_RoleName`` is populated correctly in App Insights.

    After configuring the Azure Monitor exporter the following
    instrumentations are applied:

    - ``FastAPIInstrumentor`` — wraps inbound HTTP requests so that each
      request generates a ``requests`` span with automatic exception capture
      and upstream dependency correlation.
    - ``SQLAlchemyInstrumentor`` — wraps every SQLAlchemy Core statement so
      that DB round-trips appear as ``dependency`` spans in the Application
      Map.  Requires a synchronous Engine; the async engine exposes one via
      ``.sync_engine``.
    - ``AsyncPGInstrumentor`` — hooks asyncpg at the library level so that
      low-level PostgreSQL wire calls are captured even when SQLAlchemy is
      bypassed (e.g. raw ``asyncpg.connect`` usage in migrations).

    Args:
        app: The FastAPI application instance to instrument.  When *None*
            no FastAPI instrumentation is applied (useful for non-HTTP
            processes or unit tests that only verify the monitor call).
        engine: The SQLAlchemy ``AsyncEngine`` instance.  When provided,
            ``SQLAlchemyInstrumentor`` is wired to ``engine.sync_engine``
            so that SQL statements appear as dependency spans.  When *None*
            SQLAlchemy instrumentation is skipped.
    """
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection_string:
        logger.debug("APPLICATIONINSIGHTS_CONNECTION_STRING not set" " — telemetry disabled.")
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            logger_name="app",  # collect logs from 'app' namespace + children
        )
        logger.info("Azure Monitor OpenTelemetry configured for backend.")

        if app is not None:
            from opentelemetry.instrumentation.fastapi import (
                FastAPIInstrumentor,
            )

            FastAPIInstrumentor().instrument_app(app)
            logger.info("FastAPI instrumented for OpenTelemetry tracing.")

        if engine is not None:
            from opentelemetry.instrumentation.sqlalchemy import (
                SQLAlchemyInstrumentor,
            )

            SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
            logger.info("SQLAlchemy instrumented for OpenTelemetry DB dependency" " tracing.")

        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
        logger.info("asyncpg instrumented for OpenTelemetry DB dependency tracing.")

    # Catch-all: telemetry init failures must never crash the app.
    # Azure SDK init can raise ValueError (bad connection string),
    # ConnectionError (network), or ImportError (missing optional deps).
    # A failure here is always logged at ERROR and then swallowed.
    except Exception:  # pragma: no cover
        logger.exception(
            "Failed to configure Azure Monitor OpenTelemetry;" " continuing without telemetry."
        )
