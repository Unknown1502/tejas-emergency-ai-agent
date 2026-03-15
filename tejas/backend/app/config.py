"""
Configuration management for the Tejas backend.

Loads settings from environment variables with validation and sensible defaults.
Uses pydantic-settings for type-safe configuration with .env file support.
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """Deployment environment enumeration."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All Google Cloud credentials and project identifiers are required
    for production deployment. In development, some can be omitted and
    the application will use local emulators or defaults.
    """

    # ---------------------
    # Application
    # ---------------------
    app_name: str = "Tejas"
    app_version: str = "1.0.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"

    # ---------------------
    # Server
    # ---------------------
    host: str = "0.0.0.0"
    port: int = 8080
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    # ---------------------
    # Google Cloud Platform
    # ---------------------
    gcp_project_id: str = Field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        description="Google Cloud project ID for all GCP services",
    )
    gcp_region: str = Field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_REGION", "us-central1"),
        description="GCP region for Vertex AI and Cloud Run",
    )

    # ---------------------
    # Gemini Live API
    # ---------------------
    gemini_model: str = Field(
        default="gemini-2.5-flash-native-audio-latest",
        description="Gemini model identifier for the Live API",
    )
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="API key for Gemini. If unset, defaults to Vertex AI auth.",
    )
    use_vertex_ai: bool = Field(
        default=True,
        description="Use Vertex AI endpoint instead of direct API key auth",
    )

    # ---------------------
    # Gemini Audio Settings
    # ---------------------
    audio_sample_rate: int = Field(
        default=16000,
        description="Audio sample rate in Hz for PCM capture",
    )
    audio_channels: int = 1
    audio_chunk_duration_ms: int = Field(
        default=100,
        description="Duration of each audio chunk sent to Gemini in milliseconds",
    )
    voice_name: str = Field(
        default="Orus",
        description="Prebuilt voice for Gemini audio responses. Orus is deep and authoritative.",
    )

    # ---------------------
    # Video Settings
    # ---------------------
    video_fps_min: int = Field(default=2, description="Minimum frames per second")
    video_fps_max: int = Field(default=5, description="Maximum frames per second")
    video_frame_width: int = 1280
    video_frame_height: int = 720
    video_frame_quality: int = Field(
        default=70,
        description="JPEG quality (0-100) for video frames sent to Gemini",
    )

    # ---------------------
    # Firestore
    # ---------------------
    firestore_database: str = Field(
        default="(default)",
        description="Firestore database ID. Use (default) for the default database.",
    )
    firestore_incidents_collection: str = "incidents"
    firestore_victims_collection: str = "victims"
    firestore_dispatches_collection: str = "dispatches"
    firestore_hazmat_collection: str = "hazmat_data"
    firestore_protocols_collection: str = "medical_protocols"

    # ---------------------
    # Cloud Storage
    # ---------------------
    gcs_bucket_name: str = Field(
        default="",
        description="Cloud Storage bucket for scene captures and audio logs",
    )

    # ---------------------
    # Google Maps Platform
    # ---------------------
    google_maps_api_key: str = Field(
        default="",
        description="API key for Google Maps Places API (nearest hospital lookup)",
    )

    # ---------------------
    # Session Management
    # ---------------------
    session_timeout_seconds: int = Field(
        default=1800,
        description="Maximum duration of a single incident session (30 minutes)",
    )
    max_concurrent_sessions: int = Field(
        default=50,
        description="Maximum number of concurrent WebSocket sessions",
    )

    # ---------------------
    # Proactive Scene Scanning
    # ---------------------
    proactive_scan_interval_seconds: int = Field(
        default=30,
        description=(
            "Interval in seconds between proactive scene re-assessments. "
            "The agent silently re-scans the video feed on this cadence even "
            "without user input."
        ),
    )

    # ---------------------
    # WebSocket
    # ---------------------
    ws_ping_interval: int = Field(
        default=20,
        description="WebSocket ping interval in seconds to keep connection alive",
    )
    ws_heartbeat_interval: int = Field(
        default=30,
        description="Interval in seconds between session heartbeat/metrics messages",
    )
    ws_max_message_size: int = Field(
        default=1_048_576,
        description="Maximum WebSocket message size in bytes (1 MB)",
    )

    @field_validator("gcp_project_id")
    @classmethod
    def validate_project_id_in_production(cls, v: str, info) -> str:
        """Ensure GCP project ID is set in non-development environments."""
        env = info.data.get("environment", Environment.DEVELOPMENT)
        if env != Environment.DEVELOPMENT and not v:
            raise ValueError(
                "GCP_PROJECT_ID must be set in staging and production environments"
            )
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Normalize and validate log level."""
        v = v.upper()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached singleton of application settings.

    Uses lru_cache to ensure settings are loaded only once from
    environment variables and .env file. Subsequent calls return
    the same instance.
    """
    return Settings()
