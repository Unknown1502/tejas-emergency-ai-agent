"""
FastAPI application for the Tejas emergency scene intelligence agent.

Exposes:
- WebSocket endpoint for bidirectional audio/video streaming
- REST endpoints for health checks, session info, and data seeding
- CORS middleware for frontend communication
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.stream_manager import get_stream_manager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application Lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown logic for the FastAPI application.
    """
    settings = get_settings()
    logger.info(
        "Tejas backend starting: env=%s, port=%d",
        settings.environment.value,
        settings.port,
    )
    yield
    # Shutdown: close all streaming sessions
    manager = get_stream_manager()
    await manager.shutdown_all()
    logger.info("Tejas backend shut down.")


# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Tejas",
        description="Emergency Scene Intelligence Agent -- Gemini Live API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment.value != "production" else None,
        redoc_url="/redoc" if settings.environment.value != "production" else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    _register_routes(app)

    return app


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _register_routes(app: FastAPI) -> None:
    """Register all HTTP and WebSocket routes."""

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/health", tags=["health"])
    async def health_check():
        """
        Health check endpoint for Cloud Run and load balancers.
        Returns 200 if the service is running.
        """
        manager = get_stream_manager()
        return {
            "status": "healthy",
            "service": "tejas",
            "version": "1.0.0",
            "active_sessions": manager.active_count,
        }

    @app.get("/ready", tags=["health"])
    async def readiness_check():
        """
        Readiness probe. Verifies that dependencies are reachable.
        """
        checks = {"genai_sdk": True, "firestore": True}

        # Verify GenAI SDK availability
        try:
            from app.agent import get_genai_client
            get_genai_client()
        except Exception as e:
            checks["genai_sdk"] = False
            logger.warning("GenAI SDK not ready: %s", e)

        # Verify Firestore availability
        try:
            from app.database import get_database
            db = get_database()
            # Light read to verify connection
        except Exception as e:
            checks["firestore"] = False
            logger.warning("Firestore not ready: %s", e)

        all_ready = all(checks.values())
        return JSONResponse(
            status_code=status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "ready" if all_ready else "not_ready",
                "checks": checks,
            },
        )

    # ------------------------------------------------------------------
    # Session Info
    # ------------------------------------------------------------------

    @app.get("/api/sessions", tags=["sessions"])
    async def get_sessions():
        """Return the count of active streaming sessions."""
        manager = get_stream_manager()
        return {"active_sessions": manager.active_count}

    # ------------------------------------------------------------------
    # Data Seeding
    # ------------------------------------------------------------------

    @app.post("/api/seed", tags=["data"])
    async def seed_data():
        """
        Seed Firestore with hazmat and medical protocol reference data.
        Intended for initial setup or development environments.
        """
        import json, os
        from app.database import get_database

        db = get_database()
        try:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            with open(os.path.join(data_dir, "hazmat_erg.json"), "r") as f:
                hazmat_entries = json.load(f)
            with open(os.path.join(data_dir, "medical_protocols.json"), "r") as f:
                protocol_entries = json.load(f)
            hazmat_count = db.seed_hazmat_data(hazmat_entries)
            protocol_count = db.seed_medical_protocols(protocol_entries)
            return {"status": "seeded", "message": f"Loaded {hazmat_count} hazmat entries and {protocol_count} protocols into Firestore."}
        except Exception as e:
            logger.exception("Seed data failed")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"status": "error", "message": str(e)},
            )

    # ------------------------------------------------------------------
    # WebSocket Streaming Endpoint
    # ------------------------------------------------------------------

    @app.websocket("/ws/stream")
    async def websocket_stream(websocket: WebSocket):
        """
        Bidirectional WebSocket endpoint for audio/video streaming.

        Protocol:
        1. Client connects and sends a `session_init` message with
           optional incident_id and GPS coordinates.
        2. Client streams audio chunks (PCM 16kHz, base64) and
           video frames (JPEG, base64) as JSON messages.
        3. Server streams back audio responses and tool call
           notifications as JSON messages.
        4. Either side can close the connection at any time.

        Message format (client -> server):
            {"type": "audio", "data": "<base64 PCM>"}
            {"type": "video", "data": "<base64 JPEG>"}
            {"type": "session_init", "data": {"incident_id": "...", "gps_lat": 0, "gps_lng": 0}}
            {"type": "text", "data": "fallback text input"}
            {"type": "end_turn"}
            {"type": "ping"}

        Message format (server -> client):
            {"type": "audio", "data": "<base64 PCM>", "mime_type": "audio/pcm"}
            {"type": "transcript", "data": "text content"}
            {"type": "tool_call", "data": {"name": "...", "args": {}, "status": "executing"}}
            {"type": "tool_result", "data": {"name": "...", "result": {}, "status": "completed"}}
            {"type": "status", "data": {"status": "...", "message": "..."}}
            {"type": "heartbeat", "data": {"session_id": "...", "uptime_seconds": 0, ...}}
            {"type": "turn_complete"}
            {"type": "error", "data": {"message": "..."}}
            {"type": "pong", "timestamp": 0}
        """
        await websocket.accept()
        logger.info("WebSocket client connected: %s", websocket.client)

        manager = get_stream_manager()
        session = await manager.create_session(websocket)

        try:
            await session.start()
        except WebSocketDisconnect:
            logger.info("Client disconnected: session_id=%s", session.session_id)
        except Exception:
            logger.exception("WebSocket error: session_id=%s", session.session_id)
        finally:
            await manager.remove_session(session.session_id)
            logger.info(
                "WebSocket session cleaned up: session_id=%s",
                session.session_id,
            )

    # ------------------------------------------------------------------
    # ADK WebSocket Endpoint (Google Agent Development Kit)
    # ------------------------------------------------------------------

    @app.websocket("/ws/adk")
    async def websocket_adk_stream(websocket: WebSocket):
        """
        ADK-native bidi-streaming endpoint.

        Uses Google Agent Development Kit's LlmAgent + LiveRequestQueue instead
        of the raw GenAI SDK. Exposes the same JSON WebSocket protocol as
        /ws/stream so the frontend works with either endpoint.

        This endpoint demonstrates ADK bidi-streaming as documented in:
            'ADK Bidi-streaming in 5 minutes'
            'ADK Bidi-streaming development guide'

        Select this endpoint via the TEJAS_USE_ADK=true environment variable,
        or connect directly from the frontend configuration.
        """
        await websocket.accept()
        logger.info("ADK WebSocket client connected: %s", websocket.client)

        from app.adk_runner import ADKStreamSession
        session = ADKStreamSession(websocket)

        try:
            await session.start()
        except WebSocketDisconnect:
            logger.info("ADK client disconnected: session_id=%s", session.session_id)
        except Exception:
            logger.exception("ADK WebSocket error: session_id=%s", session.session_id)


# ---------------------------------------------------------------------------
# Application Instance
# ---------------------------------------------------------------------------

app = create_app()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment.value == "development",
        log_level="info",
        ws_ping_interval=settings.ws_ping_interval,
        ws_ping_timeout=settings.ws_ping_interval * 3,
    )
