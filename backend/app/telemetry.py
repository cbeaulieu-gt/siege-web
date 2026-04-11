"""
Application Insights / OpenTelemetry initialisation for the backend.

Call ``configure_telemetry()`` once at process start, before the ASGI app
begins accepting requests.  If ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is
not set the function is a no-op so local development is unaffected.
"""

import logging
import os

logger = logging.getLogger(__name__)


def configure_telemetry() -> None:
    """Initialise Azure Monitor OpenTelemetry if the connection string is present.

    The ``azure-monitor-opentelemetry`` distro reads
    ``APPLICATIONINSIGHTS_CONNECTION_STRING`` from the environment automatically
    when ``configure_azure_monitor()`` is called without an explicit
    ``connection_string`` argument.  We guard the call so that a missing env var
    is a silent no-op rather than an import-time or startup error.
    """
    connection_string = os.environ.get(
        "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
    ).strip()
    if not connection_string:
        logger.debug(
            "APPLICATIONINSIGHTS_CONNECTION_STRING not set — telemetry disabled."
        )
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            logger_name="app",  # collect logs from the 'app' namespace and children
        )
        logger.info("Azure Monitor OpenTelemetry configured for backend.")
    except (
        Exception
    ):  # pragma: no cover — unexpected SDK failure must not crash the app
        logger.exception(
            "Failed to configure Azure Monitor OpenTelemetry; continuing without telemetry."
        )
