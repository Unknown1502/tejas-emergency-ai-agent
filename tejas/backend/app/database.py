"""
Firestore database client for the Tejas application.

Provides an async-friendly wrapper around Google Cloud Firestore for
managing incidents, victims, dispatches, hazmat lookups, and medical
protocol retrieval. All writes are timestamped and all reads are
type-validated through the models layer.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.config import get_settings
from app.models import (
    DispatchRecord,
    HazmatEntry,
    Incident,
    MedicalProtocol,
    SessionState,
    ToolCallLog,
    Victim,
)

logger = logging.getLogger(__name__)


class DatabaseClient:
    """
    Firestore database client providing CRUD operations
    for all Tejas domain entities.

    This client is designed to be instantiated once at application
    startup and shared across request handlers via dependency injection.
    """

    # Resolved once at first use; shared across all instances.
    _DATA_DIR = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "data")
    )
    _local_hazmat_cache: Optional[list] = None
    _local_protocol_cache: Optional[list] = None

    def __init__(self) -> None:
        settings = get_settings()
        self._project_id = settings.gcp_project_id
        self._db: Optional[firestore.Client] = None
        self._collections = {
            "incidents": settings.firestore_incidents_collection,
            "victims": settings.firestore_victims_collection,
            "dispatches": settings.firestore_dispatches_collection,
            "hazmat": settings.firestore_hazmat_collection,
            "protocols": settings.firestore_protocols_collection,
        }

    @property
    def db(self) -> firestore.Client:
        """Lazy initialization of Firestore client."""
        if self._db is None:
            settings = get_settings()
            if self._project_id:
                self._db = firestore.Client(
                    project=self._project_id,
                    database=settings.firestore_database,
                )
            else:
                # Development mode: use default credentials or emulator
                self._db = firestore.Client(
                    database=settings.firestore_database,
                )
            logger.info(
                "Firestore client initialized for project: %s",
                self._project_id or "(default)",
            )
        return self._db

    # ------------------------------------------------------------------
    # Incident Operations
    # ------------------------------------------------------------------

    def create_incident(self, incident: Incident) -> str:
        """
        Create a new incident record in Firestore.

        Returns the incident_id of the created document.
        Fails silently if Firestore is unavailable.
        """
        try:
            doc_ref = self.db.collection(self._collections["incidents"]).document(
                incident.incident_id
            )
            doc_ref.set(incident.to_firestore())
            logger.info("Created incident: %s", incident.incident_id)
        except Exception as e:
            logger.warning("Firestore create_incident failed (continuing): %s", e)
        return incident.incident_id

    def get_incident(self, incident_id: str) -> Optional[dict[str, Any]]:
        """Retrieve an incident by its ID."""
        doc = (
            self.db.collection(self._collections["incidents"])
            .document(incident_id)
            .get()
        )
        if doc.exists:
            return doc.to_dict()
        return None

    def update_incident(self, incident_id: str, updates: dict[str, Any]) -> None:
        """
        Update specific fields on an incident document.

        Automatically sets the updated_at timestamp.
        """
        try:
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.db.collection(self._collections["incidents"]).document(
                incident_id
            ).update(updates)
            logger.debug("Updated incident %s: %s", incident_id, list(updates.keys()))
        except Exception as e:
            logger.warning("Firestore update_incident failed (continuing): %s", e)

    def update_incident_state(
        self, incident_id: str, state: SessionState
    ) -> None:
        """Update the session state of an incident."""
        self.update_incident(incident_id, {"session_state": state.value})

    def add_hazard_to_incident(self, incident_id: str, hazard: str) -> None:
        """Append a hazard description to the incident's hazard list."""
        try:
            self.db.collection(self._collections["incidents"]).document(
                incident_id
            ).update(
                {
                    "hazards_identified": firestore.ArrayUnion([hazard]),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as e:
            logger.warning("Firestore add_hazard_to_incident failed (continuing): %s", e)

    def add_victim_to_incident(self, incident_id: str, victim_id: str) -> None:
        """Register a victim ID with the incident record."""
        try:
            self.db.collection(self._collections["incidents"]).document(
                incident_id
            ).update(
                {
                    "victims": firestore.ArrayUnion([victim_id]),
                    "victim_count": firestore.Increment(1),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as e:
            logger.warning("Firestore add_victim_to_incident failed (continuing): %s", e)

    def add_dispatch_to_incident(
        self, incident_id: str, dispatch_id: str
    ) -> None:
        """Register a dispatch ID with the incident record."""
        try:
            self.db.collection(self._collections["incidents"]).document(
                incident_id
            ).update(
                {
                    "dispatches": firestore.ArrayUnion([dispatch_id]),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as e:
            logger.warning("Firestore add_dispatch_to_incident failed (continuing): %s", e)

    # ------------------------------------------------------------------
    # Victim Operations
    # ------------------------------------------------------------------

    def create_victim(self, incident_id: str, victim: Victim) -> str:
        """
        Create a victim record. Fails silently if Firestore unavailable.
        """
        try:
            doc_ref = self.db.collection(self._collections["victims"]).document(
                victim.victim_id
            )
            data = victim.to_firestore()
            data["incident_id"] = incident_id
            doc_ref.set(data)
            self.add_victim_to_incident(incident_id, victim.victim_id)
            logger.info("Created victim %s for incident %s", victim.victim_id, incident_id)
        except Exception as e:
            logger.warning("Firestore create_victim failed (continuing): %s", e)
        return victim.victim_id

    def update_victim(self, victim_id: str, updates: dict[str, Any]) -> None:
        """Update specific fields on a victim record."""
        try:
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.db.collection(self._collections["victims"]).document(
                victim_id
            ).update(updates)
        except Exception as e:
            logger.warning("Firestore update_victim failed (continuing): %s", e)

    def get_victim(self, victim_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a victim record by ID. Returns None silently if Firestore unavailable."""
        try:
            doc = (
                self.db.collection(self._collections["victims"])
                .document(victim_id)
                .get()
            )
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.warning("Firestore get_victim failed (continuing): %s", e)
            return None

    def get_victims_for_incident(self, incident_id: str) -> list[dict[str, Any]]:
        """Retrieve all victim records associated with an incident."""
        results = (
            self.db.collection(self._collections["victims"])
            .where(filter=FieldFilter("incident_id", "==", incident_id))
            .stream()
        )
        return [doc.to_dict() for doc in results]

    # ------------------------------------------------------------------
    # Dispatch Operations
    # ------------------------------------------------------------------

    def create_dispatch(
        self, incident_id: str, dispatch: DispatchRecord
    ) -> str:
        """
        Create a dispatch record and link it to the incident.
        Fails silently if Firestore unavailable.
        """
        try:
            doc_ref = self.db.collection(self._collections["dispatches"]).document(
                dispatch.dispatch_id
            )
            data = dispatch.to_firestore()
            data["incident_id"] = incident_id
            doc_ref.set(data)
            self.add_dispatch_to_incident(incident_id, dispatch.dispatch_id)
            logger.info(
                "Created dispatch %s (%s) for incident %s",
                dispatch.dispatch_id,
                dispatch.resource_type.value,
                incident_id,
            )
        except Exception as e:
            logger.warning("Firestore create_dispatch failed (continuing): %s", e)
        return dispatch.dispatch_id

    def get_dispatches_for_incident(
        self, incident_id: str
    ) -> list[dict[str, Any]]:
        """Retrieve all dispatch records for an incident."""
        results = (
            self.db.collection(self._collections["dispatches"])
            .where(filter=FieldFilter("incident_id", "==", incident_id))
            .stream()
        )
        return [doc.to_dict() for doc in results]

    # ------------------------------------------------------------------
    # Hazmat Database Operations
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Local JSON helpers (fallback when Firestore unavailable)
    # ------------------------------------------------------------------

    @classmethod
    def _get_local_hazmat(cls) -> list:
        if cls._local_hazmat_cache is None:
            path = os.path.join(cls._DATA_DIR, "hazmat_erg.json")
            try:
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f)
                # Normalize JSON field names to match Firestore schema expected by tools.py
                normalized = []
                for entry in raw:
                    n = dict(entry)
                    # chemical_name → name
                    if "chemical_name" in n and "name" not in n:
                        n["name"] = n.pop("chemical_name")
                    # safe_distance_ft → safe_distance_feet
                    if "safe_distance_ft" in n and "safe_distance_feet" not in n:
                        n["safe_distance_feet"] = n.pop("safe_distance_ft")
                    # guide_number → erg_guide_number
                    if "guide_number" in n and "erg_guide_number" not in n:
                        n["erg_guide_number"] = n.pop("guide_number")
                    # ppe_required: list → comma-separated string
                    if isinstance(n.get("ppe_required"), list):
                        n["ppe_required"] = "; ".join(n["ppe_required"])
                    # first_aid: list → newline-separated string
                    if isinstance(n.get("first_aid"), list):
                        n["first_aid"] = "\n".join(n["first_aid"])
                    # add name_lower for name-based search
                    n["name_lower"] = n.get("name", "").strip().lower()
                    normalized.append(n)
                cls._local_hazmat_cache = normalized
                logger.info("Loaded %d hazmat entries from local JSON", len(cls._local_hazmat_cache))
            except Exception as e:
                logger.warning("Could not load local hazmat JSON: %s", e)
                cls._local_hazmat_cache = []
        return cls._local_hazmat_cache

    @classmethod
    def _get_local_protocols(cls) -> list:
        if cls._local_protocol_cache is None:
            path = os.path.join(cls._DATA_DIR, "medical_protocols.json")
            try:
                with open(path, encoding="utf-8") as f:
                    cls._local_protocol_cache = json.load(f)
                logger.info("Loaded %d protocols from local JSON", len(cls._local_protocol_cache))
            except Exception as e:
                logger.warning("Could not load local protocol JSON: %s", e)
                cls._local_protocol_cache = []
        return cls._local_protocol_cache

    def get_hazmat_by_un_number(self, un_number: str) -> Optional[dict[str, Any]]:
        """
        Look up a hazardous material by its UN identification number.

        The un_number should be in the format 'UNXXXX' (e.g., 'UN1203').
        Normalizes the input to uppercase for consistent matching.
        Gracefully falls back to local JSON if Firestore is unavailable.
        """
        un_number = un_number.upper().strip()
        if not un_number.startswith("UN"):
            un_number = f"UN{un_number}"

        try:
            doc = (
                self.db.collection(self._collections["hazmat"])
                .document(un_number)
                .get()
            )
            if doc.exists:
                logger.info("Hazmat lookup hit (Firestore): %s", un_number)
                return doc.to_dict()
        except Exception as e:
            logger.warning("Firestore hazmat lookup failed, using local JSON: %s", e)

        # Local JSON fallback
        for entry in self._get_local_hazmat():
            if entry.get("un_number", "").upper() == un_number:
                logger.info("Hazmat lookup hit (local JSON): %s", un_number)
                return entry

        logger.warning("Hazmat lookup miss: %s", un_number)
        return None

    def get_hazmat_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """
        Look up a hazardous material by its common name.

        Performs a case-insensitive search. Falls back to local JSON.
        """
        name_lower = name.strip().lower()

        try:
            results = (
                self.db.collection(self._collections["hazmat"])
                .where(filter=FieldFilter("name_lower", "==", name_lower))
                .limit(1)
                .stream()
            )
            for doc in results:
                logger.info("Hazmat lookup by name hit (Firestore): %s", name)
                return doc.to_dict()
        except Exception as e:
            logger.warning("Firestore hazmat name lookup failed, using local JSON: %s", e)

        # Local JSON fallback — match on name or name_lower field
        for entry in self._get_local_hazmat():
            entry_name = entry.get("name", "").lower()
            if name_lower in entry_name or entry_name in name_lower:
                logger.info("Hazmat lookup by name hit (local JSON): %s", name)
                return entry

        logger.warning("Hazmat lookup by name miss: %s", name)
        return None

    # ------------------------------------------------------------------
    # Medical Protocol Operations
    # ------------------------------------------------------------------

    def get_medical_protocol(
        self, injury_type: str, severity_level: str
    ) -> Optional[dict[str, Any]]:
        """
        Retrieve a medical first-aid protocol by injury type and severity.

        Returns the most specific matching protocol. Falls back to
        local JSON if Firestore is unavailable.
        """
        injury_type_lower = injury_type.strip().lower()
        severity_lower = severity_level.strip().lower()

        try:
            # Attempt exact match first
            results = (
                self.db.collection(self._collections["protocols"])
                .where(filter=FieldFilter("injury_type", "==", injury_type_lower))
                .where(filter=FieldFilter("severity_level", "==", severity_lower))
                .limit(1)
                .stream()
            )
            for doc in results:
                logger.info("Protocol lookup hit (Firestore): %s / %s", injury_type, severity_level)
                return doc.to_dict()

            # Fallback: match injury type only
            results = (
                self.db.collection(self._collections["protocols"])
                .where(filter=FieldFilter("injury_type", "==", injury_type_lower))
                .limit(1)
                .stream()
            )
            for doc in results:
                logger.info("Protocol lookup partial hit (Firestore): %s", injury_type)
                return doc.to_dict()
        except Exception as e:
            logger.warning("Firestore protocol lookup failed, using local JSON: %s", e)

        # Local JSON fallback
        best: Optional[dict] = None
        for entry in self._get_local_protocols():
            etype = entry.get("injury_type", "").lower()
            if etype == injury_type_lower:
                if entry.get("severity_level", "").lower() == severity_lower:
                    logger.info("Protocol lookup exact hit (local JSON): %s/%s", injury_type, severity_lower)
                    return entry
                best = entry  # type-only match; keep for fallback
        if best:
            logger.info("Protocol lookup partial hit (local JSON): %s", injury_type)
            return best

        logger.warning("Protocol lookup miss: %s / %s", injury_type, severity_level)
        return None

    # ------------------------------------------------------------------
    # Tool Call Logging
    # ------------------------------------------------------------------

    def log_tool_call(self, incident_id: str, log_entry: ToolCallLog) -> None:
        """
        Append a tool call log entry. Fails silently if Firestore unavailable.
        """
        try:
            self.db.collection(self._collections["incidents"]).document(
                incident_id
            ).collection("tool_calls").add(log_entry.to_firestore())
        except Exception as e:
            logger.warning("Firestore log_tool_call failed (continuing): %s", e)

    # ------------------------------------------------------------------
    # Bulk Operations (for data seeding)
    # ------------------------------------------------------------------

    def seed_hazmat_data(self, entries: list[dict[str, Any]]) -> int:
        """
        Bulk insert hazmat entries into Firestore.

        Each entry must have a 'un_number' field used as the document ID.
        Returns the number of entries written.
        """
        batch = self.db.batch()
        count = 0

        for entry in entries:
            un_number = entry.get("un_number", "").upper().strip()
            if not un_number:
                continue
            doc_ref = self.db.collection(self._collections["hazmat"]).document(
                un_number
            )
            # Add lowercase name field for name-based lookups
            entry["name_lower"] = entry.get("name", "").strip().lower()
            batch.set(doc_ref, entry)
            count += 1

            # Firestore batch limit is 500 writes
            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()

        if count % 400 != 0:
            batch.commit()

        logger.info("Seeded %d hazmat entries", count)
        return count

    def seed_medical_protocols(self, protocols: list[dict[str, Any]]) -> int:
        """
        Bulk insert medical protocol entries into Firestore.

        Returns the number of entries written.
        """
        batch = self.db.batch()
        count = 0

        for protocol in protocols:
            protocol_id = protocol.get(
                "protocol_id", f"{protocol.get('injury_type', 'unknown')}_{count}"
            )
            doc_ref = self.db.collection(self._collections["protocols"]).document(
                protocol_id
            )
            batch.set(doc_ref, protocol)
            count += 1

            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()

        if count % 400 != 0:
            batch.commit()

        logger.info("Seeded %d medical protocols", count)
        return count


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_db_client: Optional[DatabaseClient] = None


def get_database() -> DatabaseClient:
    """
    Return the module-level DatabaseClient singleton.

    Initializes on first call. Thread-safe due to Python GIL
    for attribute assignment.
    """
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client
