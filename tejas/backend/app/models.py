"""
Pydantic models for the Tejas application.

Defines data structures for incidents, victims, dispatches, hazmat records,
medical protocols, and WebSocket message envelopes. These models serve as
the single source of truth for data shapes across the backend.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class VictimStatus(str, Enum):
    """START triage classification for victim status."""

    IMMEDIATE = "immediate"       # Red tag - life-threatening, needs immediate intervention
    DELAYED = "delayed"           # Yellow tag - serious but can wait
    MINOR = "minor"               # Green tag - walking wounded
    DECEASED = "deceased"         # Black tag - no signs of life
    UNKNOWN = "unknown"           # Not yet assessed


class ResourceType(str, Enum):
    """Types of emergency resources that can be dispatched."""

    AMBULANCE = "ambulance"
    FIRE_TRUCK = "fire_truck"
    HAZMAT_UNIT = "hazmat_unit"
    POLICE = "police"
    HELICOPTER = "helicopter"


class SeverityLevel(str, Enum):
    """Severity classification for dispatch priority."""

    CRITICAL = "critical"
    URGENT = "urgent"
    MODERATE = "moderate"


class InjurySeverity(str, Enum):
    """Severity classification for injuries."""

    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    LIFE_THREATENING = "life_threatening"


class HospitalSpecialty(str, Enum):
    """Hospital specialty types for routing."""

    TRAUMA = "trauma"
    BURN = "burn"
    PEDIATRIC = "pediatric"
    GENERAL = "general"
    CARDIAC = "cardiac"


class SessionState(str, Enum):
    """State of a WebSocket incident session."""

    CONNECTING = "connecting"
    ACTIVE = "active"
    PAUSED = "paused"
    DISCONNECTED = "disconnected"
    TERMINATED = "terminated"


# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------


class GeoLocation(BaseModel):
    """GPS coordinates with optional accuracy."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: Optional[float] = None


class Victim(BaseModel):
    """Record of an identified victim in the incident."""

    victim_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: VictimStatus = VictimStatus.UNKNOWN
    injuries: str = ""
    treatment_given: str = ""
    location_description: str = ""
    triage_tag: Optional[str] = None
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_firestore(self) -> dict:
        """Serialize to Firestore-compatible dictionary."""
        data = self.model_dump()
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data


class DispatchRecord(BaseModel):
    """Record of a dispatched emergency resource."""

    dispatch_id: str = Field(default_factory=lambda: f"DSP-{uuid.uuid4().hex[:6].upper()}")
    resource_type: ResourceType
    severity: SeverityLevel
    location: GeoLocation
    notes: str = ""
    estimated_eta_minutes: Optional[int] = None
    status: str = "dispatched"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_firestore(self) -> dict:
        """Serialize to Firestore-compatible dictionary."""
        data = self.model_dump()
        data["resource_type"] = self.resource_type.value
        data["severity"] = self.severity.value
        data["location"] = {
            "latitude": self.location.latitude,
            "longitude": self.location.longitude,
            "accuracy_meters": self.location.accuracy_meters,
        }
        data["created_at"] = self.created_at.isoformat()
        return data


class Incident(BaseModel):
    """Top-level incident record aggregating all scene data."""

    incident_id: str = Field(default_factory=lambda: f"INC-{uuid.uuid4().hex[:8].upper()}")
    location: Optional[GeoLocation] = None
    summary: str = ""
    victim_count: int = 0
    hazards_identified: list[str] = Field(default_factory=list)
    dispatches: list[str] = Field(default_factory=list)  # dispatch IDs
    victims: list[str] = Field(default_factory=list)      # victim IDs
    session_state: SessionState = SessionState.CONNECTING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_firestore(self) -> dict:
        """Serialize to Firestore-compatible dictionary."""
        data = self.model_dump()
        data["session_state"] = self.session_state.value
        if self.location:
            data["location"] = {
                "latitude": self.location.latitude,
                "longitude": self.location.longitude,
                "accuracy_meters": self.location.accuracy_meters,
            }
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data


class HazmatEntry(BaseModel):
    """Hazardous material database entry from USDOT ERG."""

    un_number: str = Field(..., description="UN identification number (e.g. UN1203)")
    name: str = Field(..., description="Chemical common name")
    hazard_class: str = ""
    division: str = ""
    description: str = ""
    flash_point: str = ""
    boiling_point: str = ""
    toxicity: str = ""
    safe_distance_feet: int = 0
    large_spill_distance_feet: int = 0
    ppe_required: str = ""
    fire_response: str = ""
    spill_response: str = ""
    first_aid: str = ""
    erg_guide_number: str = ""


class MedicalProtocol(BaseModel):
    """First-aid protocol entry from AHA/Red Cross guidelines."""

    protocol_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    injury_type: str = Field(..., description="Type of injury (e.g. hemorrhage, fracture)")
    severity_level: str = Field(..., description="Severity: minor, moderate, severe, life_threatening")
    title: str = ""
    steps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    when_to_call_ems: str = ""
    source: str = ""


class HospitalResult(BaseModel):
    """Result from nearest hospital lookup."""

    name: str
    address: str = ""
    distance_miles: float = 0.0
    estimated_eta_minutes: int = 0
    specialty: HospitalSpecialty = HospitalSpecialty.GENERAL
    phone: str = ""
    is_trauma_center: bool = False


# ---------------------------------------------------------------------------
# WebSocket Message Envelopes
# ---------------------------------------------------------------------------


class WSMessageType(str, Enum):
    """Types of messages exchanged over the WebSocket connection."""

    # Client -> Server
    AUDIO_CHUNK = "audio_chunk"
    VIDEO_FRAME = "video_frame"
    GPS_UPDATE = "gps_update"
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # Server -> Client
    AUDIO_RESPONSE = "audio_response"
    INCIDENT_UPDATE = "incident_update"
    DISPATCH_NOTIFICATION = "dispatch_notification"
    TOOL_CALL_LOG = "tool_call_log"
    ERROR = "error"
    SESSION_READY = "session_ready"
    CONNECTION_ACK = "connection_ack"


class WSMessage(BaseModel):
    """
    Envelope for all WebSocket messages.

    Binary payloads (audio, video) are sent as raw binary frames.
    Structured messages use this JSON envelope.
    """

    type: WSMessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    incident_id: Optional[str] = None

    def to_json_str(self) -> str:
        """Serialize to JSON string for WebSocket transmission."""
        return self.model_dump_json()


class ToolCallLog(BaseModel):
    """Log entry for a tool call made by the Gemini agent."""

    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    duration_ms: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_firestore(self) -> dict:
        """Serialize to Firestore-compatible dictionary."""
        data = self.model_dump()
        data["timestamp"] = self.timestamp.isoformat()
        return data
