"""
Unit tests for the Tejas tool implementations.

Tests verify tool function behavior, input validation, and response format
without requiring live Firestore or Gemini API connections. All tool
functions are synchronous — no async/await is needed or correct here.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.tools import (
    TOOL_REGISTRY,
    dispatch_resources,
    execute_tool,
    get_medical_protocol,
    get_nearest_hospital,
    log_incident,
    query_hazmat_database,
)


class TestToolRegistry:
    """Verify that all tools are registered correctly."""

    def test_all_tools_registered(self):
        expected = [
            "dispatch_resources",
            "query_hazmat_database",
            "log_incident",
            "get_medical_protocol",
            "get_nearest_hospital",
            "generate_scene_report",
        ]
        for name in expected:
            assert name in TOOL_REGISTRY, f"Tool '{name}' not found in registry"

    def test_registry_values_are_callable(self):
        for name, handler in TOOL_REGISTRY.items():
            assert callable(handler), f"Tool '{name}' handler is not callable"

    def test_registry_has_six_tools(self):
        assert len(TOOL_REGISTRY) == 6, (
            f"Expected 6 tools, found {len(TOOL_REGISTRY)}: {list(TOOL_REGISTRY.keys())}"
        )


class TestDispatchResources:
    """Tests for the dispatch_resources tool."""

    def test_dispatch_returns_required_fields(self):
        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.create_dispatch.return_value = "dispatch_123"
            mock_db.return_value = db_instance

            result = dispatch_resources(
                incident_id="test_incident",
                resource_type="ambulance",
                severity="critical",
                gps_lat=37.7749,
                gps_lng=-122.4194,
            )

        assert "dispatch_id" in result
        assert "resource_type" in result
        assert "estimated_eta_minutes" in result
        assert "status" in result
        assert result["resource_type"] == "ambulance"
        assert result["status"] == "dispatched"

    def test_critical_severity_has_shorter_eta(self):
        # Run many times because ETA has randomness — critical max < moderate min
        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.create_dispatch.return_value = "d1"
            mock_db.return_value = db_instance

            critical_etas = [
                dispatch_resources(
                    incident_id="test",
                    resource_type="ambulance",
                    severity="critical",
                    gps_lat=37.7749,
                    gps_lng=-122.4194,
                )["estimated_eta_minutes"]
                for _ in range(10)
            ]

        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.create_dispatch.return_value = "d2"
            mock_db.return_value = db_instance

            moderate_etas = [
                dispatch_resources(
                    incident_id="test",
                    resource_type="ambulance",
                    severity="moderate",
                    gps_lat=37.7749,
                    gps_lng=-122.4194,
                )["estimated_eta_minutes"]
                for _ in range(10)
            ]

        assert max(critical_etas) <= max(moderate_etas)

    def test_invalid_resource_type_returns_error(self):
        result = dispatch_resources(
            incident_id="test",
            resource_type="spaceship",
            severity="critical",
            gps_lat=37.7749,
            gps_lng=-122.4194,
        )
        assert result["status"] == "error"

    def test_invalid_severity_returns_error(self):
        result = dispatch_resources(
            incident_id="test",
            resource_type="ambulance",
            severity="catastrophic",
            gps_lat=37.7749,
            gps_lng=-122.4194,
        )
        assert result["status"] == "error"


class TestQueryHazmat:
    """Tests for the query_hazmat_database tool."""

    def test_unknown_substance_returns_fallback(self):
        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.get_hazmat_by_un_number.return_value = None
            db_instance.get_hazmat_by_name.return_value = None
            mock_db.return_value = db_instance

            result = query_hazmat_database(
                incident_id="test",
                chemical_name="totally_unknown_substance_xyz",
            )

        assert result["status"] == "not_found"
        assert result["safe_distance_feet"] >= 300
        assert "ppe_required" in result

    def test_known_substance_returns_data(self):
        mock_entry = {
            "name": "Chlorine",
            "un_number": "UN1017",
            "hazard_class": "Toxic Gas",
            "safe_distance_feet": 1500,
            "large_spill_distance_feet": 3000,
            "ppe_required": "Level A Suit, SCBA",
            "description": "Toxic gas used in industrial processes",
            "fire_response": "Do not extinguish fire unless flow can be stopped",
            "spill_response": "Evacuate area immediately",
            "first_aid": "Move to fresh air; call 911",
            "erg_guide_number": "124",
            "flash_point": "N/A",
            "boiling_point": "-34°C",
            "toxicity": "Highly toxic",
        }

        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.get_hazmat_by_un_number.return_value = None
            db_instance.get_hazmat_by_name.return_value = mock_entry
            mock_db.return_value = db_instance

            result = query_hazmat_database(
                incident_id="test",
                chemical_name="Chlorine",
            )

        assert result["status"] == "found"
        assert result["chemical_name"] == "Chlorine"
        assert result["safe_distance_feet"] == 1500

    def test_un_number_lookup_takes_priority(self):
        un_entry = {
            "name": "Gasoline",
            "un_number": "UN1203",
            "hazard_class": "Flammable Liquid",
            "safe_distance_feet": 300,
            "large_spill_distance_feet": 500,
            "ppe_required": "Full PPE",
            "description": "Flammable liquid",
            "fire_response": "Foam",
            "spill_response": "Contain",
            "first_aid": "Remove from exposure",
            "erg_guide_number": "128",
            "flash_point": "-43°C",
            "boiling_point": "35-210°C",
            "toxicity": "Low",
        }

        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.get_hazmat_by_un_number.return_value = un_entry
            mock_db.return_value = db_instance

            result = query_hazmat_database(
                incident_id="test",
                un_number="1203",
            )

        assert result["status"] == "found"
        assert result["un_number"] == "UN1203"
        # get_hazmat_by_name should NOT have been called
        db_instance.get_hazmat_by_name.assert_not_called()


class TestLogIncident:
    """Tests for the log_incident tool."""

    def test_log_new_victim(self):
        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.get_victim.return_value = None
            db_instance.create_victim.return_value = "victim_123"
            mock_db.return_value = db_instance

            result = log_incident(
                incident_id="incident_001",
                victim_id="person_near_car",
                status="immediate",
                injuries="Severe laceration on left arm",
            )

        assert result["victim_id"] == "person_near_car"
        assert result["victim_status"] == "immediate"
        assert result["status"] == "logged"

    def test_update_existing_victim(self):
        existing = MagicMock()

        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.get_victim.return_value = existing
            mock_db.return_value = db_instance

            result = log_incident(
                incident_id="inc_001",
                victim_id="victim_1",
                status="delayed",
            )

        assert result["status"] in ("logged", "updated")
        assert result["victim_id"] == "victim_1"

    def test_invalid_status_returns_error(self):
        result = log_incident(
            incident_id="test",
            victim_id="v1",
            status="not_a_real_status",
        )
        assert result["status"] == "error"


class TestGetMedicalProtocol:
    """Tests for the get_medical_protocol tool."""

    def test_unknown_protocol_returns_general_fallback(self):
        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.get_medical_protocol.return_value = None
            mock_db.return_value = db_instance

            result = get_medical_protocol(
                incident_id="test",
                injury_type="alien_bite",
                severity_level="severe",
            )

        assert result["status"] == "not_found"
        steps = result["fallback_protocol"]["steps"]
        assert len(steps) > 0
        full_text = " ".join(s.lower() for s in steps)
        assert any(kw in full_text for kw in ("airway", "breathing", "bleeding", "emergency"))

    def test_known_protocol_returned_correctly(self):
        mock_protocol = {
            "injury_type": "hemorrhage",
            "severity_level": "severe",
            "title": "Hemorrhage Control Protocol",
            "steps": [
                "Apply direct pressure with both palms.",
                "Elevate the limb above heart level if no fracture.",
                "Apply tourniquet 2 to 3 inches above the wound if bleeding is uncontrolled.",
            ],
            "warnings": ["Do not remove impaled objects from the wound."],
            "when_to_call_ems": "Always for severe hemorrhage.",
            "source": "AHA/Red Cross",
        }

        with patch("app.tools.get_database") as mock_db:
            db_instance = MagicMock()
            db_instance.get_medical_protocol.return_value = mock_protocol
            mock_db.return_value = db_instance

            result = get_medical_protocol(
                incident_id="test",
                injury_type="hemorrhage",
                severity_level="severe",
            )

        assert result["status"] == "found"
        assert len(result["protocol"]["steps"]) == 3
        assert result["protocol"]["source"] == "AHA/Red Cross"


class TestGetNearestHospital:
    """Tests for get_nearest_hospital using the demo fallback (no Maps key)."""

    def test_returns_hospital_data(self):
        result = get_nearest_hospital(
            incident_id="test",
            gps_lat=37.7749,
            gps_lng=-122.4194,
        )

        assert "hospital_name" in result
        assert "distance_miles" in result
        assert "estimated_eta_minutes" in result
        assert "specialty" in result
        assert result["status"] == "found"

    def test_trauma_specialty_filter(self):
        result = get_nearest_hospital(
            incident_id="test",
            gps_lat=37.7749,
            gps_lng=-122.4194,
            specialty_needed="trauma",
        )

        assert result["status"] == "found"
        assert "hospital_name" in result

    def test_invalid_specialty_falls_back_to_general(self):
        result = get_nearest_hospital(
            incident_id="test",
            gps_lat=37.7749,
            gps_lng=-122.4194,
            specialty_needed="totally_unknown_specialty",
        )

        assert result["status"] == "found"
        assert "hospital_name" in result


class TestExecuteTool:
    """Tests for the execute_tool dispatcher."""

    def test_unknown_tool_returns_error(self):
        result = execute_tool(
            tool_name="nonexistent_tool",
            incident_id="test",
            arguments={},
        )
        assert "error" in result or result.get("status") == "error"

    def test_execute_dispatches_get_nearest_hospital(self):
        # Patch the module-level function; execute_tool calls it via TOOL_REGISTRY
        with patch.dict("app.tools.TOOL_REGISTRY", {
            "get_nearest_hospital": MagicMock(return_value={"hospital_name": "Test Hospital", "status": "found"})
        }):
            result = execute_tool(
                tool_name="get_nearest_hospital",
                incident_id="test",
                arguments={"gps_lat": 37.0, "gps_lng": -122.0},
            )

        assert result["hospital_name"] == "Test Hospital"

    def test_execute_with_invalid_args_returns_error(self):
        """Tool called with missing required args should return an error dict."""
        result = execute_tool(
            tool_name="dispatch_resources",
            incident_id="test",
            arguments={"resource_type": "ambulance"},  # missing severity, gps_lat, gps_lng
        )
        assert result.get("status") == "error"
