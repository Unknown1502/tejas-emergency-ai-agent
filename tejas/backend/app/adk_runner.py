"""
Google Agent Development Kit (ADK) bidi-streaming integration for Tejas.

This module provides an alternative session driver that uses Google ADK's
LlmAgent and LiveRequestQueue for bidirectional audio/video streaming,
in addition to the direct GenAI SDK approach in stream_manager.py.

ADK bidi-streaming architecture:
    1. An LlmAgent is configured with the Tejas system prompt and all 6 tools.
    2. A Runner manages session state and routes events between the agent,
       the client WebSocket, and the LiveRequestQueue.
    3. Per WebSocket connection, a LiveRequestQueue is created and fed with
       real-time audio chunks and JPEG video frames from the responder's device.
    4. The Runner yields events (text, audio, interruptions, tool calls) which
       are forwarded to the WebSocket client.

Usage (alternative to stream_manager.py):
    from app.adk_runner import create_adk_session, run_adk_session

References:
    - https://google.github.io/adk-docs/streaming/
    - Challenge resource: "ADK Bidi-streaming in 5 minutes"
    - Challenge resource: "ADK Bidi-streaming development guide"
"""

import asyncio
import base64
import json
import logging
import uuid
from typing import Any, AsyncIterator, List, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ADK Tool Wrappers
# ---------------------------------------------------------------------------
# Each function below wraps a Tejas tool implementation so that ADK's
# function-calling runtime can invoke it. ADK automatically introspects
# docstrings and type hints to build the function schema.


def adk_dispatch_resources(
    resource_type: str,
    severity: str,
    gps_lat: float,
    gps_lng: float,
    notes: str = "",
    incident_id: str = "unknown",
) -> dict:
    """
    Dispatch emergency resources (ambulance, fire_truck, hazmat_unit, police,
    helicopter) to the incident scene. Call proactively when resources are needed.

    Args:
        resource_type: Type of resource — ambulance, fire_truck, hazmat_unit,
            police, or helicopter.
        severity: critical, urgent, or moderate.
        gps_lat: Latitude of the destination.
        gps_lng: Longitude of the destination.
        notes: Additional context for the dispatch crew.
        incident_id: Active incident identifier (injected by the runner).
    """
    from app.tools import dispatch_resources
    return dispatch_resources(
        incident_id=incident_id,
        resource_type=resource_type,
        severity=severity,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        notes=notes,
    )


def adk_query_hazmat_database(
    chemical_name: str = "",
    un_number: str = "",
    incident_id: str = "unknown",
) -> dict:
    """
    Query the USDOT Emergency Response Guidebook for hazardous material safety
    data. Call IMMEDIATELY when any chemical container, label, or UN number is
    visible. Never guess chemical properties.

    Args:
        chemical_name: Common chemical name (e.g. 'gasoline', 'chlorine').
        un_number: UN identification number (e.g. 'UN1203' or '1203').
        incident_id: Active incident identifier.
    """
    from app.tools import query_hazmat_database
    return query_hazmat_database(
        incident_id=incident_id,
        chemical_name=chemical_name,
        un_number=un_number,
    )


def adk_log_incident(
    victim_id: str,
    status: str,
    injuries: str = "",
    treatment_given: str = "",
    location_description: str = "",
    notes: str = "",
    incident_id: str = "unknown",
) -> dict:
    """
    Log or update a victim's triage status in the real-time incident record.
    Call for every victim found. status must be one of: immediate, delayed,
    minor, deceased, unknown.

    Args:
        victim_id: Descriptive ID (e.g. 'victim_1', 'person_near_car').
        status: START triage classification.
        injuries: Observed injuries.
        treatment_given: Treatment given so far.
        location_description: Where the victim is located.
        notes: Other observations.
        incident_id: Active incident identifier.
    """
    from app.tools import log_incident
    return log_incident(
        incident_id=incident_id,
        victim_id=victim_id,
        status=status,
        injuries=injuries,
        treatment_given=treatment_given,
        location_description=location_description,
        notes=notes,
    )


def adk_get_medical_protocol(
    injury_type: str,
    severity_level: str,
    incident_id: str = "unknown",
) -> dict:
    """
    Retrieve a standard first-aid protocol for a specific injury type and
    severity. Always call this before giving medical instructions. Never invent
    procedures.

    Args:
        injury_type: Type of injury (hemorrhage, fracture, burn, cardiac_arrest,
            choking, concussion, laceration, sprain, hypothermia, heat_stroke).
        severity_level: minor, moderate, severe, or life_threatening.
        incident_id: Active incident identifier.
    """
    from app.tools import get_medical_protocol
    return get_medical_protocol(
        incident_id=incident_id,
        injury_type=injury_type,
        severity_level=severity_level,
    )


def adk_get_nearest_hospital(
    gps_lat: float,
    gps_lng: float,
    specialty_needed: str = "trauma",
    incident_id: str = "unknown",
) -> dict:
    """
    Find the nearest hospital with the required specialty. Call when a victim
    needs hospital-level care.

    Args:
        gps_lat: Latitude of the incident.
        gps_lng: Longitude of the incident.
        specialty_needed: trauma, burn, pediatric, general, or cardiac.
        incident_id: Active incident identifier.
    """
    from app.tools import get_nearest_hospital
    return get_nearest_hospital(
        incident_id=incident_id,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        specialty_needed=specialty_needed,
    )


def adk_generate_scene_report(
    scene_description: str,
    victim_count: int = 0,
    incident_id: str = "unknown",
) -> dict:
    """
    Generate a tactical overhead scene map image using Google Imagen 3 (GenAI
    Media). Call after the full scene assessment is complete and you can
    describe the spatial layout of victims, hazards, and resources.

    Args:
        scene_description: Spatial description of the scene for Imagen. Include
            hazards, victim positions, and resource staging areas in this text.
        victim_count: Number of victims on scene.
        incident_id: Active incident identifier.
    """
    from app.tools import generate_scene_report
    return generate_scene_report(
        incident_id=incident_id,
        scene_description=scene_description,
        hazards_identified=None,
        victim_count=victim_count,
    )


# ---------------------------------------------------------------------------
# ADK Agent Factory
# ---------------------------------------------------------------------------


def build_adk_agent():
    """
    Build and return the Tejas LlmAgent configured for bidi-streaming.

    Returns an ADK LlmAgent wrapping Gemini 2.0 Flash Live with all 6
    Tejas tools registered as ADK FunctionTools.
    """
    try:
        from google.adk.agents import LlmAgent
        from google.adk.tools import FunctionTool
    except ImportError as exc:
        raise ImportError(
            "google-adk is required for ADK bidi-streaming. "
            "Install it with: pip install google-adk"
        ) from exc

    from app.agent import SYSTEM_INSTRUCTION
    from app.config import get_settings

    settings = get_settings()

    tejas_tools = [
        FunctionTool(adk_dispatch_resources),
        FunctionTool(adk_query_hazmat_database),
        FunctionTool(adk_log_incident),
        FunctionTool(adk_get_medical_protocol),
        FunctionTool(adk_get_nearest_hospital),
        FunctionTool(adk_generate_scene_report),   # GenMedia / Imagen 3
    ]

    agent = LlmAgent(
        name="tejas",
        model=settings.gemini_model,
        instruction=SYSTEM_INSTRUCTION,
        tools=tejas_tools,
    )

    logger.info(
        "ADK LlmAgent built: model=%s, tools=%d",
        settings.gemini_model,
        len(tejas_tools),
    )
    return agent


# ---------------------------------------------------------------------------
# ADK Session Runner
# ---------------------------------------------------------------------------


class ADKStreamSession:
    """
    Manages a single ADK bidi-streaming session between a WebSocket client
    and the Tejas LlmAgent via Google ADK's LiveRequestQueue.

    This is the ADK-native counterpart to stream_manager.StreamSession.
    Both expose the same WebSocket protocol so the frontend works unchanged.
    """

    def __init__(
        self,
        websocket: WebSocket,
        session_id: Optional[str] = None,
    ) -> None:
        self.websocket = websocket
        self.session_id = session_id or str(uuid.uuid4())
        self.incident_id: Optional[str] = None
        self.gps_lat: float | None = None
        self.gps_lng: float | None = None
        self._shutdown = asyncio.Event()

        logger.info("ADKStreamSession created: session_id=%s", self.session_id)

    async def start(self) -> None:
        """
        Construct the ADK Runner, open a live session, and bridge
        audio/video frames between the WebSocket and the LiveRequestQueue.
        """
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.adk.agents.live_request_queue import LiveRequestQueue
        except ImportError:
            logger.error("google-adk not installed.")
            await self._send_error(
                "ADK runner unavailable. Reconnect to the default WebSocket endpoint."
            )
            return

        from google.adk.agents.run_config import RunConfig, StreamingMode
        from google.genai import types

        agent = build_adk_agent()
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="tejas",
            session_service=session_service,
        )

        # RunConfig for native audio models (AUDIO response modality)
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        # Get or create session (handles reconnections)
        session = await session_service.get_session(
            app_name="tejas",
            user_id=self.session_id,
            session_id=self.session_id,
        )
        if not session:
            await session_service.create_session(
                app_name="tejas",
                user_id=self.session_id,
                session_id=self.session_id,
            )

        await self._send_status("connected", "ADK bidi-streaming session active.")

        live_queue = LiveRequestQueue()

        # Run two concurrent coroutines: read from client / read from ADK.
        await asyncio.gather(
            self._client_to_queue(live_queue),
            self._runner_to_client(runner, live_queue, run_config),
        )

    async def _client_to_queue(self, live_queue) -> None:
        """Read WebSocket messages and push audio/video into the LiveRequestQueue."""
        from google.genai import types as genai_types
        from app.config import get_settings
        settings = get_settings()

        try:
            while not self._shutdown.is_set():
                raw = await self.websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "audio":
                    audio_bytes = base64.b64decode(msg.get("data", ""))
                    live_queue.send_realtime(
                        genai_types.Blob(
                            mime_type=f"audio/pcm;rate={settings.audio_sample_rate}",
                            data=audio_bytes,
                        )
                    )

                elif msg_type == "video":
                    frame_bytes = base64.b64decode(msg.get("data", ""))
                    live_queue.send_realtime(
                        genai_types.Blob(
                            mime_type="image/jpeg",
                            data=frame_bytes,
                        )
                    )

                elif msg_type == "session_init":
                    data = msg.get("data", {})
                    self.incident_id = data.get("incident_id")
                    self.gps_lat = data.get("gps_lat")
                    self.gps_lng = data.get("gps_lng")
                    await self._send_status(
                        "session_initialized",
                        f"ADK session ready. Incident: {self.incident_id}",
                    )

                elif msg_type == "end_turn":
                    live_queue.close()
                    break

                elif msg_type == "ping":
                    await self._send_json({"type": "pong"})

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("ADK client_to_queue error: session=%s", self.session_id)

    async def _runner_to_client(self, runner, live_queue, run_config) -> None:
        """Stream ADK events back to the WebSocket client."""
        try:
            async for event in runner.run_live(
                user_id=self.session_id,
                session_id=self.session_id,
                live_request_queue=live_queue,
                run_config=run_config,
            ):
                # Skip events that have no content
                content = getattr(event, "content", None)
                if not content:
                    # Turn complete signal (no content)
                    if getattr(event, "turn_complete", False) or (
                        hasattr(event, "is_final_response") and event.is_final_response()
                    ):
                        await self._send_json({"type": "turn_complete"})
                    continue

                parts = getattr(content, "parts", []) or []

                for part in parts:
                    # ── Audio response ──────────────────────────────────────
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data is not None:
                        audio_bytes = getattr(inline_data, "data", None)
                        if audio_bytes:
                            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
                            mime = getattr(inline_data, "mime_type", "audio/pcm")
                            await self._send_json({
                                "type": "audio",
                                "data": audio_b64,
                                "mime_type": mime,
                            })

                    # ── Text / transcript ───────────────────────────────────
                    text = getattr(part, "text", None)
                    if text:
                        await self._send_json({
                            "type": "transcript",
                            "data": text,
                        })

                    # ── Function call notification to client ────────────────
                    function_call = getattr(part, "function_call", None)
                    if function_call is not None:
                        fn_name = getattr(function_call, "name", "")
                        fn_args = dict(getattr(function_call, "args", {}) or {})
                        await self._send_json({
                            "type": "tool_call",
                            "data": {
                                "name": fn_name,
                                "args": fn_args,
                                "status": "executing",
                            },
                        })

                    # ── Function response (tool result) ─────────────────────
                    function_response = getattr(part, "function_response", None)
                    if function_response is not None:
                        fn_name = getattr(function_response, "name", "")
                        result = dict(getattr(function_response, "response", {}) or {})

                        await self._send_json({
                            "type": "tool_result",
                            "data": {
                                "name": fn_name,
                                "result": result,
                                "status": "completed",
                            },
                        })

                        # Relay Imagen scene map to HUD
                        if fn_name == "adk_generate_scene_report" or fn_name == "generate_scene_report":
                            if result.get("status") == "generated" and result.get("image_b64"):
                                await self._send_json({
                                    "type": "scene_image",
                                    "data": {
                                        "image_b64": result["image_b64"],
                                        "mime_type": result.get("mime_type", "image/jpeg"),
                                        "scene_description": result.get("scene_description", ""),
                                        "victim_count": result.get("victim_count", 0),
                                        "hazards": result.get("hazards", []),
                                        "incident_id": self.incident_id,
                                    },
                                })
                                logger.info(
                                    "ADK: Imagen scene image broadcast to client: session=%s",
                                    self.session_id,
                                )

                # Turn complete
                if getattr(event, "turn_complete", False) or (
                    hasattr(event, "is_final_response") and event.is_final_response()
                ):
                    await self._send_json({"type": "turn_complete"})

        except Exception:
            logger.exception("ADK runner_to_client error: session=%s", self.session_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _send_json(self, data: dict) -> None:
        try:
            await self.websocket.send_text(json.dumps(data, default=str))
        except Exception:
            logger.warning("ADK session: failed to send message")

    async def _send_status(self, status: str, message: str) -> None:
        await self._send_json({
            "type": "status",
            "data": {"status": status, "message": message},
        })

    async def _send_error(self, message: str) -> None:
        await self._send_json({
            "type": "error",
            "data": {"message": message},
        })
