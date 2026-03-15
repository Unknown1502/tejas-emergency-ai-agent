"""
Bidirectional stream manager for the Tejas application.

Orchestrates the data flow between a WebSocket client and a Gemini
Live API session. Manages three concurrent async tasks:

1. client_to_gemini: Receives audio/video from the WebSocket and
   forwards it to the Gemini Live session.
2. gemini_to_client: Receives audio responses and tool call requests
   from Gemini, executes tools, returns results, and streams audio
   back to the client.
3. heartbeat: Keeps the session alive with periodic pings and
   monitors connection health.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import random
import time
import uuid
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from app.agent import build_live_config, get_genai_client
from app.config import get_settings
from app.models import SessionState, WSMessage, WSMessageType
from app.tools import execute_tool

logger = logging.getLogger(__name__)


class StreamSession:
    """
    Represents a single bidirectional streaming session between a
    WebSocket client and the Gemini Live API.

    Lifecycle:
    1. Client connects via WebSocket.
    2. StreamSession is created, opens a Gemini Live session.
    3. Three concurrent tasks run until the client disconnects
       or a fatal error occurs.
    4. On teardown, all tasks are cancelled and resources released.
    """

    def __init__(self, websocket: WebSocket, session_id: Optional[str] = None):
        self.websocket = websocket
        self.session_id = session_id or str(uuid.uuid4())
        self.state = SessionState.CONNECTING
        self.settings = get_settings()

        # Gemini Live session handle (set during start)
        self._gemini_session: Any = None

        # Async tasks
        self._tasks: list[asyncio.Task] = []

        # Metrics
        self._audio_chunks_sent = 0
        self._audio_chunks_received = 0
        self._video_frames_sent = 0
        self._tool_calls_executed = 0
        self._start_time: Optional[float] = None

        # Cancellation event
        self._shutdown = asyncio.Event()

        # Incident context -- set by client on session init
        self.incident_id: Optional[str] = None
        self.gps_lat: Optional[float] = None
        self.gps_lng: Optional[float] = None

        logger.info("StreamSession created: session_id=%s", self.session_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """
        Open the Gemini Live session and start the bidirectional
        streaming tasks. Blocks until the session ends.
        """
        self._start_time = time.monotonic()

        try:
            self.state = SessionState.CONNECTING
            await self._send_status("connecting", "Initializing Gemini Live session...")

            client = get_genai_client()
            config = build_live_config()

            async with client.aio.live.connect(
                model=self.settings.gemini_model,
                config=config,
            ) as session:
                self._gemini_session = session
                self.state = SessionState.ACTIVE
                await self._send_status("connected", "Gemini Live session active.")

                logger.info(
                    "Gemini Live session opened: session_id=%s, model=%s",
                    self.session_id,
                    self.settings.gemini_model,
                )

                # Launch concurrent tasks
                self._tasks = [
                    asyncio.create_task(
                        self._client_to_gemini(),
                        name=f"c2g-{self.session_id[:8]}",
                    ),
                    asyncio.create_task(
                        self._gemini_to_client(),
                        name=f"g2c-{self.session_id[:8]}",
                    ),
                    asyncio.create_task(
                        self._heartbeat(),
                        name=f"hb-{self.session_id[:8]}",
                    ),
                    asyncio.create_task(
                        self._proactive_scan(),
                        name=f"scan-{self.session_id[:8]}",
                    ),
                ]

                # Wait for any task to finish (usually means disconnect)
                done, pending = await asyncio.wait(
                    self._tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # If a task raised an exception, log it
                for task in done:
                    if task.exception():
                        logger.error(
                            "Task %s failed: %s",
                            task.get_name(),
                            task.exception(),
                        )

                # Cancel remaining tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        except WebSocketDisconnect:
            logger.info("Client disconnected: session_id=%s", self.session_id)
        except Exception:
            logger.exception("Session error: session_id=%s", self.session_id)
            await self._send_error("Session error. Please reconnect.")
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """Signal the session to shut down gracefully."""
        self._shutdown.set()

    # ------------------------------------------------------------------
    # Client -> Gemini
    # ------------------------------------------------------------------

    async def _client_to_gemini(self) -> None:
        """
        Receive messages from the WebSocket client and forward
        audio chunks and video frames to the Gemini Live session.
        """
        logger.info("client_to_gemini task started: session_id=%s", self.session_id)

        try:
            while not self._shutdown.is_set():
                raw = await self.websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "audio":
                    await self._handle_client_audio(msg)

                elif msg_type == "video":
                    await self._handle_client_video(msg)

                elif msg_type == "session_init":
                    await self._handle_session_init(msg)

                elif msg_type == "end_turn":
                    # Client signals end of their speech turn
                    if self._gemini_session:
                        await self._gemini_session.send(
                            input=".",
                            end_of_turn=True,
                        )

                elif msg_type == "text":
                    # Text input fallback
                    text = msg.get("data", "")
                    if text and self._gemini_session:
                        await self._gemini_session.send(
                            input=text,
                            end_of_turn=True,
                        )
                        logger.debug("Sent text to Gemini: %s", text[:100])

                elif msg_type == "ping":
                    await self._send_json({"type": "pong", "timestamp": time.time()})

                else:
                    logger.warning("Unknown client message type: %s", msg_type)

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected in client_to_gemini")
        except asyncio.CancelledError:
            logger.info("client_to_gemini cancelled")
        except Exception:
            logger.exception("Error in client_to_gemini")

    async def _handle_client_audio(self, msg: dict) -> None:
        """Forward a base64-encoded PCM audio chunk to Gemini."""
        audio_b64 = msg.get("data", "")
        if not audio_b64 or not self._gemini_session:
            return

        audio_bytes = base64.b64decode(audio_b64)

        await self._gemini_session.send(
            input=types.LiveClientRealtimeInput(
                media_chunks=[
                    types.MediaChunk(
                        data=audio_bytes,
                        mime_type=f"audio/pcm;rate={self.settings.audio_sample_rate}",
                    )
                ]
            )
        )
        self._audio_chunks_sent += 1

    async def _handle_client_video(self, msg: dict) -> None:
        """Forward a base64-encoded JPEG video frame to Gemini."""
        frame_b64 = msg.get("data", "")
        if not frame_b64 or not self._gemini_session:
            return

        frame_bytes = base64.b64decode(frame_b64)

        await self._gemini_session.send(
            input=types.LiveClientRealtimeInput(
                media_chunks=[
                    types.MediaChunk(
                        data=frame_bytes,
                        mime_type="image/jpeg",
                    )
                ]
            )
        )
        self._video_frames_sent += 1

    async def _handle_session_init(self, msg: dict) -> None:
        """Process session initialization data from the client."""
        data = msg.get("data", {})
        self.incident_id = data.get("incident_id", self.incident_id)
        self.gps_lat = data.get("gps_lat", self.gps_lat)
        self.gps_lng = data.get("gps_lng", self.gps_lng)

        # Create the incident document in Firestore so that tool writes
        # (add_hazard_to_incident, add_victim_to_incident, etc.) succeed.
        if self.incident_id:
            from app.database import get_database
            from app.models import Incident, GeoLocation

            db = get_database()
            location = None
            if self.gps_lat is not None and self.gps_lng is not None:
                location = GeoLocation(latitude=self.gps_lat, longitude=self.gps_lng)
            incident = Incident(
                incident_id=self.incident_id,
                location=location,
                summary=f"Incident {self.incident_id} created via live session {self.session_id}",
            )
            db.create_incident(incident)

        logger.info(
            "Session initialized: incident_id=%s, gps=(%s, %s)",
            self.incident_id,
            self.gps_lat,
            self.gps_lng,
        )
        await self._send_status(
            "session_initialized",
            f"Session ready. Incident: {self.incident_id}",
        )

    # ------------------------------------------------------------------
    # Gemini -> Client
    # ------------------------------------------------------------------

    async def _gemini_to_client(self) -> None:
        """
        Receive responses from the Gemini Live session and route
        them to the WebSocket client. Handles three response types:

        - Audio data: streamed back to client for playback
        - Tool calls: executed locally, results returned to Gemini
        - Text/other: forwarded as metadata to client
        """
        logger.info("gemini_to_client task started: session_id=%s", self.session_id)

        try:
            while not self._shutdown.is_set():
                if not self._gemini_session:
                    await asyncio.sleep(0.1)
                    continue

                turn = self._gemini_session.receive()
                async for response in turn:
                    await self._process_gemini_response(response)

        except asyncio.CancelledError:
            logger.info("gemini_to_client cancelled")
        except Exception:
            logger.exception("Error in gemini_to_client")

    async def _process_gemini_response(self, response: Any) -> None:
        """
        Route a single Gemini response to the appropriate handler.
        """
        # Handle server content (audio/text)
        server_content = getattr(response, "server_content", None)
        if server_content is not None:
            await self._handle_server_content(server_content)
            return

        # Handle tool calls
        tool_call = getattr(response, "tool_call", None)
        if tool_call is not None:
            await self._handle_tool_call(tool_call)
            return

        # Handle tool call cancellation
        tool_call_cancellation = getattr(response, "tool_call_cancellation", None)
        if tool_call_cancellation is not None:
            logger.info("Tool call cancelled by Gemini")
            return

        # Handle setup complete signal
        setup_complete = getattr(response, "setup_complete", None)
        if setup_complete is not None:
            logger.info("Gemini setup complete")
            await self._send_status("gemini_ready", "Gemini model ready.")
            return

    async def _handle_server_content(self, content: Any) -> None:
        """
        Process server content from Gemini -- typically audio data
        or text transcription.
        """
        model_turn = getattr(content, "model_turn", None)
        if model_turn is None:
            return

        parts = getattr(model_turn, "parts", [])
        if not parts:
            return

        for part in parts:
            # Audio response
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None:
                audio_bytes = inline_data.data
                if audio_bytes:
                    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
                    await self._send_json({
                        "type": "audio",
                        "data": audio_b64,
                        "mime_type": getattr(inline_data, "mime_type", "audio/pcm"),
                    })
                    self._audio_chunks_received += 1

            # Text response (if any)
            text = getattr(part, "text", None)
            if text:
                await self._send_json({
                    "type": "transcript",
                    "data": text,
                })

        # Check if the model is done speaking (turn complete)
        turn_complete = getattr(content, "turn_complete", False)
        if turn_complete:
            await self._send_json({"type": "turn_complete"})

    async def _handle_tool_call(self, tool_call: Any) -> None:
        """
        Execute a Gemini function call and return the result.

        This is the critical integration point between Gemini's
        intelligence and the application's grounded data sources.
        """
        function_calls = getattr(tool_call, "function_calls", [])

        for fc in function_calls:
            fn_name = fc.name
            fn_args = dict(fc.args) if fc.args else {}
            call_id = getattr(fc, "id", str(uuid.uuid4()))

            logger.info(
                "Tool call: name=%s, args=%s, call_id=%s",
                fn_name,
                json.dumps(fn_args, default=str)[:200],
                call_id,
            )

            # Notify client that a tool is being executed
            await self._send_json({
                "type": "tool_call",
                "data": {
                    "name": fn_name,
                    "args": fn_args,
                    "status": "executing",
                },
            })

            # Inject session context into tool args
            if self.incident_id:
                fn_args.setdefault("incident_id", self.incident_id)
            if self.gps_lat is not None:
                fn_args.setdefault("gps_lat", self.gps_lat)
            if self.gps_lng is not None:
                fn_args.setdefault("gps_lng", self.gps_lng)

            # Execute the tool
            try:
                result = execute_tool(
                    tool_name=fn_name,
                    arguments=fn_args,
                    incident_id=self.incident_id,
                )
                self._tool_calls_executed += 1
            except Exception as e:
                logger.exception("Tool execution failed: %s", fn_name)
                result = {"error": str(e), "tool": fn_name}

            # Return result to Gemini
            await self._gemini_session.send(
                input=types.LiveClientToolResponse(
                    function_responses=[
                        types.FunctionResponse(
                            name=fn_name,
                            id=call_id,
                            response=result,
                        )
                    ]
                )
            )

            # Notify client of tool result
            await self._send_json({
                "type": "tool_result",
                "data": {
                    "name": fn_name,
                    "result": result,
                    "status": "completed",
                },
            })

            # GenMedia: if this is a scene map from Imagen, send it as a dedicated
            # scene_image message so the frontend can display it in the HUD.
            if fn_name == "generate_scene_report":
                img_status = result.get("status")
                if img_status == "generated":
                    image_b64 = result.get("image_b64", "")
                    if image_b64:
                        await self._send_json({
                            "type": "scene_image",
                            "data": {
                                "image_b64": image_b64,
                                "mime_type": result.get("mime_type", "image/jpeg"),
                                "scene_description": result.get("scene_description", ""),
                                "victim_count": result.get("victim_count", 0),
                                "hazards": result.get("hazards", []),
                                "incident_id": self.incident_id,
                            },
                        })
                        logger.info(
                            "Scene image broadcast to client: session_id=%s, bytes=%d",
                            self.session_id,
                            len(image_b64),
                        )
                else:
                    # Imagen was unavailable — push a transcript note so the UI shows feedback
                    err_msg = result.get("message", "Scene image generation failed.")
                    await self._send_json({
                        "type": "transcript",
                        "data": f"[Scene Map] {err_msg}",
                    })
                    logger.warning(
                        "Imagen returned status=%s for session=%s: %s",
                        img_status, self.session_id, err_msg,
                    )

            logger.info(
                "Tool result returned: name=%s, success=%s",
                fn_name,
                "error" not in result,
            )

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def _heartbeat(self) -> None:
        """
        Send periodic heartbeat messages and monitor session health.
        """
        interval = self.settings.ws_heartbeat_interval
        logger.info(
            "Heartbeat task started: session_id=%s, interval=%ds",
            self.session_id,
            interval,
        )

        try:
            while not self._shutdown.is_set():
                await asyncio.sleep(interval)

                elapsed = time.monotonic() - (self._start_time or time.monotonic())
                await self._send_json({
                    "type": "heartbeat",
                    "data": {
                        "session_id": self.session_id,
                        "uptime_seconds": round(elapsed, 1),
                        "audio_chunks_sent": self._audio_chunks_sent,
                        "audio_chunks_received": self._audio_chunks_received,
                        "video_frames_sent": self._video_frames_sent,
                        "tool_calls_executed": self._tool_calls_executed,
                    },
                })

        except asyncio.CancelledError:
            logger.info("Heartbeat cancelled")

    async def _proactive_scan(self) -> None:
        """
        Periodically inject a silent proactive analysis prompt into the Gemini session.

        This makes the agent's visual hazard detection DETERMINISTIC, not probabilistic.
        Every scan_interval seconds, Gemini is instructed to scan the current video frame for:
        - UN hazmat placards or chemical containers
        - New victims or changes in victim status
        - Structural hazards or fire spread

        Without this, the agent might not notice a hazmat placard until asked.
        With this, visual detection is guaranteed within the scan interval.

        A ±20% random jitter is applied so that concurrent sessions do not all
        fire proactive scans simultaneously under load.
        """
        scan_interval = self.settings.proactive_scan_interval_seconds

        # Stagger initial delay per session to spread load: random(0.5 * interval, interval)
        initial_delay = random.uniform(scan_interval * 0.5, scan_interval)
        await asyncio.sleep(initial_delay)

        logger.info(
            "Proactive scan task started: session_id=%s, interval=%ds, initial_delay=%.1fs",
            self.session_id,
            scan_interval,
            initial_delay,
        )

        SCAN_PROMPT = (
            "[SYSTEM SCAN] Silently analyze the current video frame. "
            "If you see ANY of the following, announce it immediately and take action: "
            "(1) A UN hazmat placard, number, or chemical container label — call query_hazmat_database. "
            "(2) A new victim or change in a known victim's status — call log_incident. "
            "(3) Fire spread, structural collapse, or a new physical threat — warn the responder. "
            "If the scene is unchanged and safe, say nothing. Do not repeat information already given."
        )

        try:
            while not self._shutdown.is_set():
                # Apply ±20% jitter to spread concurrent sessions across time
                jittered_interval = scan_interval * random.uniform(0.8, 1.2)
                await asyncio.sleep(jittered_interval)

                if not self._gemini_session or self._shutdown.is_set():
                    continue

                try:
                    await self._gemini_session.send(
                        input=SCAN_PROMPT,
                        end_of_turn=True,
                    )
                    logger.debug(
                        "Proactive scan injected: session_id=%s", self.session_id
                    )
                except Exception:
                    logger.debug("Proactive scan skipped (session busy)")

        except asyncio.CancelledError:
            logger.info("Proactive scan cancelled")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _send_json(self, data: dict) -> None:
        """Send a JSON message to the WebSocket client."""
        try:
            await self.websocket.send_text(json.dumps(data, default=str))
        except Exception:
            logger.warning("Failed to send message to client")

    async def _send_status(self, status: str, message: str) -> None:
        """Send a status update to the client."""
        await self._send_json({
            "type": "status",
            "data": {"status": status, "message": message},
        })

    async def _send_error(self, message: str) -> None:
        """Send an error message to the client."""
        await self._send_json({
            "type": "error",
            "data": {"message": message},
        })

    async def _cleanup(self) -> None:
        """Release resources and log session metrics."""
        self.state = SessionState.TERMINATED
        elapsed = time.monotonic() - (self._start_time or time.monotonic())

        logger.info(
            "Session ended: session_id=%s, duration=%.1fs, "
            "audio_sent=%d, audio_recv=%d, video_sent=%d, tools=%d",
            self.session_id,
            elapsed,
            self._audio_chunks_sent,
            self._audio_chunks_received,
            self._video_frames_sent,
            self._tool_calls_executed,
        )

        # Cancel any lingering tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        self._gemini_session = None
        self._tasks.clear()


# ---------------------------------------------------------------------------
# Session Manager (manages multiple concurrent sessions)
# ---------------------------------------------------------------------------

class StreamManager:
    """
    Manages the lifecycle of all active StreamSession instances.
    Provides session creation, lookup, and cleanup.
    """

    def __init__(self):
        self._sessions: dict[str, StreamSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        websocket: WebSocket,
        session_id: Optional[str] = None,
    ) -> StreamSession:
        """Create and register a new streaming session."""
        session = StreamSession(websocket, session_id)
        async with self._lock:
            self._sessions[session.session_id] = session
        logger.info(
            "Session registered: session_id=%s, active_sessions=%d",
            session.session_id,
            len(self._sessions),
        )
        return session

    async def remove_session(self, session_id: str) -> None:
        """Remove a session from the active registry."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            await session.stop()
            logger.info(
                "Session removed: session_id=%s, active_sessions=%d",
                session_id,
                len(self._sessions),
            )

    async def get_session(self, session_id: str) -> Optional[StreamSession]:
        """Look up an active session by ID."""
        async with self._lock:
            return self._sessions.get(session_id)

    @property
    def active_count(self) -> int:
        """Return the number of active sessions."""
        return len(self._sessions)

    async def shutdown_all(self) -> None:
        """Gracefully shut down all active sessions."""
        async with self._lock:
            session_ids = list(self._sessions.keys())

        for sid in session_ids:
            await self.remove_session(sid)

        logger.info("All sessions shut down")


# Module-level singleton
_stream_manager: Optional[StreamManager] = None


def get_stream_manager() -> StreamManager:
    """Return the singleton StreamManager instance."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager
