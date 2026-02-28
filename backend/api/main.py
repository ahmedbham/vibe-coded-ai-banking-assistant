"""Banking Assistant API entry point.

Wires together all agents, MCP servers, and FastAPI routers into a single ASGI
application.  Azure Monitor OpenTelemetry instrumentation is configured here so
that it is active before any request is processed.

Environment variables
---------------------
APPLICATIONINSIGHTS_CONNECTION_STRING  (optional)
    If set, telemetry is exported to Azure Monitor / Application Insights.
    When absent, a no-op tracer provider is used (suitable for local dev).
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Observability – configure Azure Monitor OpenTelemetry before importing
# any instrumented modules so that all spans are captured.
# ---------------------------------------------------------------------------

_connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if _connection_string:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=_connection_string)
    except (ValueError, ImportError, OSError):
        logging.getLogger(__name__).warning(
            "azure-monitor-opentelemetry configuration failed; "
            "telemetry will not be exported."
        )

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

from api.chat import router as chat_router  # noqa: E402

app = FastAPI(
    title="Banking Assistant API",
    description="Multi-agent banking assistant backend API",
    version="0.1.0",
)

app.include_router(chat_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health-check endpoint."""
    return {"status": "ok"}
