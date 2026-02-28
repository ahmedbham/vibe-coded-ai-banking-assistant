"""Chat API router – POST /chat endpoint fronting the Supervisor Agent.

Accepts a JSON body ``{ "message": str, "session_id": str }`` and returns a
streaming ``text/plain`` response containing the supervisor agent's reply.

Authentication
--------------
Uses ``DefaultAzureCredential`` (Managed Identity in Azure, CLI token locally).

Observability
-------------
Each request is wrapped in an OpenTelemetry span named ``chat.request``.  The
Azure Monitor exporter is configured in ``main.py``; this module only records
spans and attributes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from pydantic import BaseModel

from agents.supervisor.agent import run_query

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request body for POST /chat."""

    message: str
    session_id: str = ""


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """Run the user message through the Supervisor Agent and stream the reply.

    The response is streamed as ``text/plain``.  In the current implementation
    the full agent reply is collected first and then yielded as a single chunk
    so that the ``StreamingResponse`` contract is honoured without requiring the
    underlying MAF workflow to expose a streaming iterator.

    Parameters
    ----------
    request:
        JSON body containing ``message`` and optional ``session_id``.

    Returns
    -------
    StreamingResponse
        A streaming ``text/plain`` response with the agent's reply.

    Raises
    ------
    HTTPException
        500 if the agent raises an unexpected exception.
    """
    with tracer.start_as_current_span("chat.request") as span:
        span.set_attribute("session_id", request.session_id)
        span.set_attribute("message.length", len(request.message))

        try:
            response_text = await run_query(request.message)
        except OSError as exc:
            # Configuration errors (e.g. missing AZURE_OPENAI_ENDPOINT)
            logger.exception("Agent configuration error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error from supervisor agent: %s", exc)
            raise HTTPException(
                status_code=500, detail="Agent error: see server logs."
            ) from exc

        span.set_attribute("response.length", len(response_text))

    async def _stream():
        yield response_text

    return StreamingResponse(_stream(), media_type="text/plain")
