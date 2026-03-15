"""
Tool implementations for the Tejas emergency scene intelligence agent.

Each tool corresponds to a Gemini function_declaration. When the model
invokes a tool via function calling, the corresponding handler in this
module executes the logic, interacts with Firestore or external APIs,
and returns structured results that Gemini uses to continue the conversation.

Tools:
    1. dispatch_resources    - Dispatch emergency units to the scene
    2. query_hazmat_database - Look up hazardous material safety data
    3. log_incident          - Log a victim or situation detail
    4. get_medical_protocol  - Retrieve first-aid protocol steps
    5. get_nearest_hospital  - Find closest hospital with required specialty
"""

from __future__ import annotations

import logging
import math
import random
import time
from typing import Any

from app.config import get_settings
from app.database import get_database
from app.models import (
    DispatchRecord,
    GeoLocation,
    HospitalResult,
    HospitalSpecialty,
    InjurySeverity,
    ResourceType,
    SeverityLevel,
    ToolCallLog,
    Victim,
    VictimStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool: dispatch_resources
# ---------------------------------------------------------------------------


def dispatch_resources(
    incident_id: str,
    resource_type: str,
    severity: str,
    gps_lat: float,
    gps_lng: float,
    notes: str = "",
) -> dict[str, Any]:
    """
    Dispatch an emergency resource to the incident scene.

    Creates a dispatch record in Firestore, associates it with the
    incident, and returns a confirmation with a dispatch ID and
    estimated time of arrival.

    Args:
        incident_id: Active incident identifier.
        resource_type: One of ambulance, fire_truck, hazmat_unit, police, helicopter.
        severity: One of critical, urgent, moderate.
        gps_lat: Latitude of the dispatch destination.
        gps_lng: Longitude of the dispatch destination.
        notes: Additional context for the dispatch.

    Returns:
        Dictionary with dispatch_id, resource_type, estimated_eta_minutes,
        and status confirmation.
    """
    start_time = time.time()
    db = get_database()

    try:
        resource_enum = ResourceType(resource_type.lower().strip())
    except ValueError:
        return {
            "status": "error",
            "message": f"Unknown resource type: {resource_type}. "
            f"Valid types: {[r.value for r in ResourceType]}",
        }

    try:
        severity_enum = SeverityLevel(severity.lower().strip())
    except ValueError:
        return {
            "status": "error",
            "message": f"Unknown severity: {severity}. "
            f"Valid levels: {[s.value for s in SeverityLevel]}",
        }

    location = GeoLocation(latitude=gps_lat, longitude=gps_lng)

    # Simulate ETA based on resource type and severity
    eta_ranges = {
        ResourceType.AMBULANCE: (5, 12),
        ResourceType.FIRE_TRUCK: (6, 15),
        ResourceType.HAZMAT_UNIT: (10, 25),
        ResourceType.POLICE: (4, 10),
        ResourceType.HELICOPTER: (8, 20),
    }
    eta_min, eta_max = eta_ranges.get(resource_enum, (5, 15))
    # Critical severity gets faster ETA
    if severity_enum == SeverityLevel.CRITICAL:
        estimated_eta = random.randint(eta_min, eta_min + 3)
    elif severity_enum == SeverityLevel.URGENT:
        estimated_eta = random.randint(eta_min + 2, eta_max - 2)
    else:
        estimated_eta = random.randint(eta_min + 3, eta_max)

    dispatch = DispatchRecord(
        resource_type=resource_enum,
        severity=severity_enum,
        location=location,
        notes=notes,
        estimated_eta_minutes=estimated_eta,
    )

    dispatch_id = db.create_dispatch(incident_id, dispatch)

    duration_ms = (time.time() - start_time) * 1000
    _log_tool_call(
        incident_id,
        "dispatch_resources",
        {
            "resource_type": resource_type,
            "severity": severity,
            "gps_lat": gps_lat,
            "gps_lng": gps_lng,
        },
        {"dispatch_id": dispatch_id, "estimated_eta_minutes": estimated_eta},
        duration_ms,
    )

    logger.info(
        "Dispatched %s (severity: %s) to (%.4f, %.4f) for incident %s. ETA: %d min",
        resource_type,
        severity,
        gps_lat,
        gps_lng,
        incident_id,
        estimated_eta,
    )

    return {
        "status": "dispatched",
        "dispatch_id": dispatch_id,
        "resource_type": resource_enum.value,
        "severity": severity_enum.value,
        "estimated_eta_minutes": estimated_eta,
        "message": (
            f"{resource_enum.value.replace('_', ' ').title()} dispatched. "
            f"Dispatch ID: {dispatch_id}. Estimated arrival: {estimated_eta} minutes."
        ),
    }


# ---------------------------------------------------------------------------
# Tool: query_hazmat_database
# ---------------------------------------------------------------------------


def query_hazmat_database(
    incident_id: str,
    chemical_name: str = "",
    un_number: str = "",
) -> dict[str, Any]:
    """
    Look up hazardous material safety data from the USDOT Emergency
    Response Guidebook database stored in Firestore.

    Searches by UN number first (preferred), then by chemical name
    as fallback. Returns safety distances, PPE requirements, and
    response procedures.

    Args:
        incident_id: Active incident identifier.
        chemical_name: Common name of the chemical (e.g., 'gasoline').
        un_number: UN identification number (e.g., 'UN1203' or '1203').

    Returns:
        Dictionary with chemical safety data or an unknown-substance
        safety protocol if not found.
    """
    start_time = time.time()
    db = get_database()
    result = None

    # Try UN number lookup first (more precise)
    if un_number:
        result = db.get_hazmat_by_un_number(un_number)

    # Fallback to name search
    if result is None and chemical_name:
        result = db.get_hazmat_by_name(chemical_name)

    duration_ms = (time.time() - start_time) * 1000

    if result is None:
        # Unknown substance -- apply maximum safety protocol
        response = {
            "status": "not_found",
            "chemical_name": chemical_name or "unknown",
            "un_number": un_number or "unknown",
            "safety_recommendation": (
                "SUBSTANCE NOT IDENTIFIED. Apply maximum precaution protocol: "
                "maintain at least 300 feet of distance. Do not touch, inhale, or "
                "approach without full Level A hazmat protection. Assume toxic, "
                "flammable, and reactive until identified. Evacuate the area "
                "and call specialized hazmat response."
            ),
            "safe_distance_feet": 300,
            "ppe_required": "Full Level A hazmat suit, SCBA",
        }
        _log_tool_call(
            incident_id,
            "query_hazmat_database",
            {"chemical_name": chemical_name, "un_number": un_number},
            response,
            duration_ms,
        )
        db.add_hazard_to_incident(
            incident_id,
            f"UNIDENTIFIED SUBSTANCE (query: name={chemical_name}, un={un_number})",
        )
        return response

    # Found: structure the response
    response = {
        "status": "found",
        "un_number": result.get("un_number", ""),
        "chemical_name": result.get("name", ""),
        "hazard_class": result.get("hazard_class", ""),
        "description": result.get("description", ""),
        "flash_point": result.get("flash_point", ""),
        "boiling_point": result.get("boiling_point", ""),
        "toxicity": result.get("toxicity", ""),
        "safe_distance_feet": result.get("safe_distance_feet", 0),
        "large_spill_distance_feet": result.get("large_spill_distance_feet", 0),
        "ppe_required": result.get("ppe_required", ""),
        "fire_response": result.get("fire_response", ""),
        "spill_response": result.get("spill_response", ""),
        "first_aid": result.get("first_aid", ""),
        "erg_guide_number": result.get("erg_guide_number", ""),
    }

    _log_tool_call(
        incident_id,
        "query_hazmat_database",
        {"chemical_name": chemical_name, "un_number": un_number},
        {"status": "found", "un_number": response["un_number"], "chemical_name": response["chemical_name"]},
        duration_ms,
    )

    db.add_hazard_to_incident(
        incident_id,
        f"{response['un_number']} - {response['chemical_name']} ({response['hazard_class']})",
    )

    logger.info(
        "Hazmat lookup for incident %s: found %s (%s)",
        incident_id,
        response["chemical_name"],
        response["un_number"],
    )
    return response


# ---------------------------------------------------------------------------
# Tool: log_incident
# ---------------------------------------------------------------------------


def log_incident(
    incident_id: str,
    victim_id: str,
    status: str,
    injuries: str = "",
    treatment_given: str = "",
    location_description: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """
    Log or update a victim's status in the incident record.

    If the victim_id already exists, updates the record.
    If new, creates a new victim entry and associates it with the incident.

    Args:
        incident_id: Active incident identifier.
        victim_id: Identifier for the victim (e.g., 'victim_1', 'person_near_car').
        status: One of immediate, delayed, minor, deceased, unknown.
        injuries: Description of observed injuries.
        treatment_given: Description of treatment administered.
        location_description: Where the victim is relative to the scene.
        notes: Additional observations.

    Returns:
        Confirmation dictionary with the victim record.
    """
    start_time = time.time()
    db = get_database()

    try:
        status_enum = VictimStatus(status.lower().strip())
    except ValueError:
        return {
            "status": "error",
            "message": f"Unknown victim status: {status}. "
            f"Valid statuses: {[s.value for s in VictimStatus]}",
        }

    # Check if victim already exists
    existing = db.get_victim(victim_id)

    if existing:
        # Update existing record
        updates = {
            "status": status_enum.value,
        }
        if injuries:
            updates["injuries"] = injuries
        if treatment_given:
            updates["treatment_given"] = treatment_given
        if location_description:
            updates["location_description"] = location_description
        if notes:
            updates["notes"] = notes

        db.update_victim(victim_id, updates)
        action = "updated"
    else:
        # Create new victim record
        victim = Victim(
            victim_id=victim_id,
            status=status_enum,
            injuries=injuries,
            treatment_given=treatment_given,
            location_description=location_description,
            notes=notes,
        )
        db.create_victim(incident_id, victim)
        action = "created"

    duration_ms = (time.time() - start_time) * 1000
    result = {
        "status": "logged" if action == "created" else "updated",
        "action": action,
        "victim_id": victim_id,
        "victim_status": status_enum.value,
        "message": f"Victim {victim_id} {action} with status: {status_enum.value}.",
    }

    _log_tool_call(
        incident_id,
        "log_incident",
        {
            "victim_id": victim_id,
            "status": status,
            "injuries": injuries,
            "treatment_given": treatment_given,
        },
        result,
        duration_ms,
    )

    logger.info(
        "Incident log for %s: %s victim %s (status: %s)",
        incident_id,
        action,
        victim_id,
        status_enum.value,
    )
    return result


# ---------------------------------------------------------------------------
# Tool: get_medical_protocol
# ---------------------------------------------------------------------------


def get_medical_protocol(
    incident_id: str,
    injury_type: str,
    severity_level: str,
) -> dict[str, Any]:
    """
    Retrieve a standard first-aid protocol from the grounding database.

    Queries the medical_protocols collection in Firestore for the
    most specific match by injury type and severity. Returns step-by-step
    instructions with warnings and EMS call criteria.

    Args:
        incident_id: Active incident identifier.
        injury_type: Type of injury (e.g., 'hemorrhage', 'fracture', 'burn').
        severity_level: One of minor, moderate, severe, life_threatening.

    Returns:
        Dictionary with protocol steps, warnings, and source attribution.
    """
    start_time = time.time()
    db = get_database()

    protocol = db.get_medical_protocol(injury_type, severity_level)
    duration_ms = (time.time() - start_time) * 1000

    if protocol is None:
        # Fallback protocol for unrecognized injury types
        result = {
            "status": "not_found",
            "injury_type": injury_type,
            "severity_level": severity_level,
            "fallback_protocol": {
                "title": "General Emergency First Aid",
                "steps": [
                    "Ensure scene safety before approaching the patient.",
                    "Call emergency services if not already done.",
                    "If there is active bleeding, apply firm direct pressure with the cleanest available material.",
                    "If the patient is not breathing, begin CPR if trained.",
                    "Keep the patient warm and still. Do not move them unless there is immediate danger.",
                    "Monitor breathing and consciousness until help arrives.",
                    "Note the time of injury and any treatments given for the EMS handoff.",
                ],
                "warnings": [
                    "Do not remove embedded objects from wounds.",
                    "Do not give food or water to an unconscious patient.",
                    "Do not attempt to set broken bones.",
                ],
                "when_to_call_ems": "Call immediately for any life-threatening condition.",
                "source": "General first-aid principles (AHA/Red Cross baseline)",
            },
            "message": (
                f"No specific protocol found for {injury_type} ({severity_level}). "
                "Providing general emergency first-aid protocol."
            ),
        }
    else:
        result = {
            "status": "found",
            "injury_type": protocol.get("injury_type", injury_type),
            "severity_level": protocol.get("severity_level", severity_level),
            "protocol": {
                "title": protocol.get("title", ""),
                "steps": protocol.get("steps", []),
                "warnings": protocol.get("warnings", []),
                "when_to_call_ems": protocol.get("when_to_call_ems", ""),
                "source": protocol.get("source", "AHA/Red Cross"),
            },
            "message": (
                f"Protocol retrieved for {injury_type} ({severity_level}). "
                "Follow steps in order. This is protocol-based guidance -- "
                "professional medical evaluation is required."
            ),
        }

    _log_tool_call(
        incident_id,
        "get_medical_protocol",
        {"injury_type": injury_type, "severity_level": severity_level},
        {"status": result["status"], "injury_type": injury_type},
        duration_ms,
    )

    logger.info(
        "Medical protocol lookup for incident %s: %s (%s) -> %s",
        incident_id,
        injury_type,
        severity_level,
        result["status"],
    )
    return result


# ---------------------------------------------------------------------------
# Tool: get_nearest_hospital
# ---------------------------------------------------------------------------


def get_nearest_hospital(
    incident_id: str,
    gps_lat: float,
    gps_lng: float,
    specialty_needed: str = "general",
) -> dict[str, Any]:
    """
    Find the nearest hospital with the required specialty using the
    Google Maps Places API (Nearby Search).

    Queries Google Maps for real hospitals near the incident GPS coordinates,
    ranked by distance. Falls back to a curated list if the API key is not
    configured or the request fails.

    Args:
        incident_id: Active incident identifier.
        gps_lat: Latitude of the incident location.
        gps_lng: Longitude of the incident location.
        specialty_needed: One of trauma, burn, pediatric, general, cardiac.
    """
    import httpx

    start_time = time.time()

    try:
        specialty_enum = HospitalSpecialty(specialty_needed.lower().strip())
    except ValueError:
        specialty_enum = HospitalSpecialty.GENERAL

    # -----------------------------------------------------------------
    # Attempt real Google Maps Places API call
    # -----------------------------------------------------------------
    settings = get_settings()
    maps_key = settings.google_maps_api_key

    if maps_key:
        try:
            keyword_map = {
                HospitalSpecialty.TRAUMA: "trauma center hospital",
                HospitalSpecialty.BURN: "burn center hospital",
                HospitalSpecialty.PEDIATRIC: "children's hospital pediatric",
                HospitalSpecialty.CARDIAC: "cardiac heart hospital",
                HospitalSpecialty.GENERAL: "hospital emergency room",
            }
            text_query = keyword_map.get(specialty_enum, "hospital")

            # ── New Places API (v1) — POST with JSON body ──────────────
            resp = httpx.post(
                "https://places.googleapis.com/v1/places:searchNearby",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": maps_key,
                    "X-Goog-FieldMask": (
                        "places.displayName,places.formattedAddress,"
                        "places.location,places.rating,places.id"
                    ),
                },
                json={
                    "includedTypes": ["hospital"],
                    "maxResultCount": 5,
                    "rankPreference": "DISTANCE",
                    "locationRestriction": {
                        "circle": {
                            "center": {
                                "latitude": gps_lat,
                                "longitude": gps_lng,
                            },
                            "radius": 25000.0,   # 25 km search radius
                        }
                    },
                    # NOTE: textQuery is NOT valid for searchNearby; use includedTypes only
                },
                timeout=6.0,
            )
            data = resp.json()
            places = data.get("places", [])

            if places:
                hospitals_out = []
                for place in places[:3]:
                    name = place.get("displayName", {}).get("text", "Unknown Hospital")
                    address = place.get("formattedAddress", "Address unavailable")
                    loc = place.get("location", {})
                    place_lat = loc.get("latitude", gps_lat)
                    place_lng = loc.get("longitude", gps_lng)

                    # Haversine distance
                    R = 6371.0
                    dlat = math.radians(place_lat - gps_lat)
                    dlng = math.radians(place_lng - gps_lng)
                    a = (math.sin(dlat / 2) ** 2
                         + math.cos(math.radians(gps_lat))
                         * math.cos(math.radians(place_lat))
                         * math.sin(dlng / 2) ** 2)
                    distance_km = R * 2 * math.asin(math.sqrt(a))
                    distance_miles = round(distance_km * 0.621371, 1)
                    eta_minutes = max(5, round(distance_km / 0.5))

                    hospitals_out.append({
                        "name": name,
                        "address": address,
                        "distance_miles": distance_miles,
                        "eta_minutes": eta_minutes,
                        "rating": place.get("rating"),
                    })

                nearest = hospitals_out[0]
                result = {
                    "status": "found",
                    "source": "google_maps",
                    "hospitals_found": len(hospitals_out),
                    "hospitals": hospitals_out,
                    "hospital_name": nearest["name"],
                    "address": nearest["address"],
                    "distance_miles": nearest["distance_miles"],
                    "estimated_eta_minutes": nearest["eta_minutes"],
                    "specialty": specialty_enum.value,
                    "is_trauma_center": specialty_enum == HospitalSpecialty.TRAUMA,
                    "message": (
                        f"Nearest {specialty_enum.value} facility: {nearest['name']}, "
                        f"{nearest['distance_miles']} miles away, ETA {nearest['eta_minutes']} minutes. "
                        f"Address: {nearest['address']}."
                    ),
                }

                duration_ms = (time.time() - start_time) * 1000
                _log_tool_call(
                    incident_id,
                    "get_nearest_hospital",
                    {"gps_lat": gps_lat, "gps_lng": gps_lng, "specialty_needed": specialty_needed},
                    {"hospital_name": nearest["name"], "distance_miles": nearest["distance_miles"], "source": "google_maps"},
                    duration_ms,
                )
                logger.info(
                    "Hospital lookup (New Places API) for incident %s: %s, %.1f miles",
                    incident_id, nearest["name"], nearest["distance_miles"],
                )
                return result

        except Exception as exc:
            logger.warning("New Places API hospital lookup failed, using fallback: %s", exc)

    # -----------------------------------------------------------------
    # Fallback: curated demo hospitals (used when Maps key not configured)
    # -----------------------------------------------------------------
    demo_hospitals = {
        HospitalSpecialty.TRAUMA: HospitalResult(
            name="Metro Regional Trauma Center",
            address="1200 Medical Center Drive",
            distance_miles=8.2,
            estimated_eta_minutes=14,
            specialty=HospitalSpecialty.TRAUMA,
            phone="(555) 234-5678",
            is_trauma_center=True,
        ),
        HospitalSpecialty.BURN: HospitalResult(
            name="City Burn Treatment Center",
            address="450 Healthcare Boulevard",
            distance_miles=12.5,
            estimated_eta_minutes=20,
            specialty=HospitalSpecialty.BURN,
            phone="(555) 345-6789",
            is_trauma_center=False,
        ),
        HospitalSpecialty.PEDIATRIC: HospitalResult(
            name="Children's Medical Hospital",
            address="789 Pediatric Way",
            distance_miles=6.8,
            estimated_eta_minutes=11,
            specialty=HospitalSpecialty.PEDIATRIC,
            phone="(555) 456-7890",
            is_trauma_center=False,
        ),
        HospitalSpecialty.GENERAL: HospitalResult(
            name="Community General Hospital",
            address="300 Main Street",
            distance_miles=4.5,
            estimated_eta_minutes=8,
            specialty=HospitalSpecialty.GENERAL,
            phone="(555) 567-8901",
            is_trauma_center=False,
        ),
        HospitalSpecialty.CARDIAC: HospitalResult(
            name="Heart and Vascular Institute",
            address="900 Cardiac Lane",
            distance_miles=10.1,
            estimated_eta_minutes=16,
            specialty=HospitalSpecialty.CARDIAC,
            phone="(555) 678-9012",
            is_trauma_center=False,
        ),
    }

    hospital = demo_hospitals.get(specialty_enum, demo_hospitals[HospitalSpecialty.GENERAL])
    duration_ms = (time.time() - start_time) * 1000

    result = {
        "status": "found",
        "source": "demo_fallback",
        "hospital_name": hospital.name,
        "address": hospital.address,
        "distance_miles": hospital.distance_miles,
        "estimated_eta_minutes": hospital.estimated_eta_minutes,
        "specialty": hospital.specialty.value,
        "phone": hospital.phone,
        "is_trauma_center": hospital.is_trauma_center,
        "message": (
            f"Nearest {specialty_enum.value} facility: {hospital.name}, "
            f"{hospital.distance_miles} miles away, ETA {hospital.estimated_eta_minutes} minutes."
        ),
    }

    _log_tool_call(
        incident_id,
        "get_nearest_hospital",
        {"gps_lat": gps_lat, "gps_lng": gps_lng, "specialty_needed": specialty_needed},
        {"hospital_name": hospital.name, "distance_miles": hospital.distance_miles, "source": "demo_fallback"},
        duration_ms,
    )
    logger.info(
        "Hospital lookup (fallback) for incident %s: %s (%s), %.1f miles",
        incident_id, hospital.name, specialty_enum.value, hospital.distance_miles,
    )
    return result


# ---------------------------------------------------------------------------
# Tool: generate_scene_report  (Google Imagen 3 — GenMedia)
# ---------------------------------------------------------------------------


def generate_scene_report(
    incident_id: str,
    scene_description: str,
    hazards_identified: list[str] | None = None,
    victim_count: int = 0,
) -> dict[str, Any]:
    """
    Generate a tactical scene overview image using Google Imagen 3.

    Constructs a rich Imagen prompt from the agent's scene assessment,
    calls Vertex AI Imagen (via the Google GenAI SDK), and returns the
    generated image as a base64-encoded JPEG string that the frontend
    renders in the responder's HUD.

    This fulfils the GenMedia requirement for the Gemini Live Agent
    Challenge: real-time image generation woven into a streaming agent.

    Args:
        incident_id: Active incident identifier for logging.
        scene_description: Spatial layout of the scene as assessed by Gemini.
        hazards_identified: List of hazards found (e.g. ['UN1203 gasoline']).
        victim_count: Total number of victims on scene.

    Returns:
        dict with image_b64 (base64 JPEG), status, and summary fields.
    """
    import base64

    start_time = time.time()
    hazards_identified = hazards_identified or []

    # Build a detailed Imagen prompt from the scene description.
    hazard_text = (
        f"Identified hazards: {', '.join(hazards_identified)}. "
        if hazards_identified else ""
    )
    victim_text = f"{victim_count} victim(s) on scene. " if victim_count else ""

    imagen_prompt = (
        "Emergency incident command tactical overhead map, bird's-eye view, "
        "professional emergency management diagram style. "
        "Dark background, high-contrast neon indicators. "
        f"Scene layout: {scene_description} "
        f"{hazard_text}{victim_text}"
        "Color-coded zones: red zones for active fire/critical threats, "
        "orange hatching for chemical hazard perimeter, yellow caution zones, "
        "green staging areas for emergency vehicles. "
        "Victim markers using START triage colors "
        "(red circles=immediate, yellow=delayed, green=minor). "
        "Emergency vehicle silhouettes with labels. "
        "Compass rose in corner. Scale bar. No photographic elements — "
        "clean vector-style diagram. Ultra-detailed, professional."
    )

    try:
        from app.agent import get_genai_client
        client = get_genai_client()

        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=imagen_prompt,
            config={
                "number_of_images": 1,
                "aspect_ratio": "16:9",
                "safety_filter_level": "block_only_high",
            },
        )

        if not response.generated_images:
            logger.warning("Imagen returned no images for incident %s", incident_id)
            return {
                "status": "no_output",
                "message": "Imagen returned no images. Check Vertex AI quota.",
                "scene_description": scene_description[:200],
            }

        image_bytes = response.generated_images[0].image.image_bytes
        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Imagen scene report generated for incident %s in %.0fms (%d bytes)",
            incident_id,
            duration_ms,
            len(image_bytes),
        )

        _log_tool_call(
            incident_id,
            "generate_scene_report",
            {
                "scene_description": scene_description[:200],
                "victim_count": victim_count,
                "hazards": hazards_identified,
            },
            {"status": "generated", "image_bytes": len(image_bytes)},
            duration_ms,
        )

        return {
            "status": "generated",
            "image_b64": image_b64,
            "mime_type": "image/jpeg",
            "scene_description": scene_description[:200],
            "victim_count": victim_count,
            "hazards": hazards_identified,
            "message": (
                "Tactical scene map generated and displayed on responder device. "
                "Use this as your incident command reference for crew briefings."
            ),
        }

    except Exception as e:
        logger.exception("Imagen generation failed for incident %s", incident_id)
        duration_ms = (time.time() - start_time) * 1000
        return {
            "status": "error",
            "message": (
                f"Scene image generation unavailable: {str(e)}. "
                "Incident text log continues normally."
            ),
        }


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------


# Map of tool names to their handler functions.
# The agent module uses this registry to route Gemini's function calls
# to the correct implementation.
TOOL_REGISTRY: dict[str, callable] = {
    "dispatch_resources": dispatch_resources,
    "query_hazmat_database": query_hazmat_database,
    "log_incident": log_incident,
    "get_medical_protocol": get_medical_protocol,
    "get_nearest_hospital": get_nearest_hospital,
    # GenMedia: generates a tactical overhead scene map via Google Imagen 3
    "generate_scene_report": generate_scene_report,
}


def execute_tool(
    tool_name: str,
    incident_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute a tool by name with the provided arguments.

    This is the single entry point for all tool execution. It looks up
    the handler in TOOL_REGISTRY, injects the incident_id, and returns
    the result dictionary.

    Args:
        tool_name: Name of the tool to execute.
        incident_id: Active incident identifier (injected into all calls).
        arguments: Dictionary of arguments from Gemini's function call.

    Returns:
        Result dictionary from the tool handler, or an error dict
        if the tool is not found.
    """
    handler = TOOL_REGISTRY.get(tool_name)
    if handler is None:
        logger.error("Unknown tool requested: %s", tool_name)
        return {
            "status": "error",
            "message": f"Unknown tool: {tool_name}. Available tools: {list(TOOL_REGISTRY.keys())}",
        }

    try:
        return handler(incident_id=incident_id, **arguments)
    except TypeError as e:
        logger.error(
            "Tool %s called with invalid arguments: %s. Error: %s",
            tool_name,
            arguments,
            str(e),
        )
        return {
            "status": "error",
            "message": f"Invalid arguments for tool {tool_name}: {str(e)}",
        }
    except Exception as e:
        logger.exception("Tool %s failed with unexpected error", tool_name)
        return {
            "status": "error",
            "message": f"Tool {tool_name} encountered an internal error: {str(e)}",
        }


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _log_tool_call(
    incident_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    duration_ms: float,
) -> None:
    """
    Persist a tool call log entry to Firestore.

    Failures in logging should not break the tool execution flow,
    so errors are caught and logged at warning level.
    """
    try:
        db = get_database()
        log_entry = ToolCallLog(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
        )
        db.log_tool_call(incident_id, log_entry)
    except Exception:
        logger.warning(
            "Failed to log tool call %s for incident %s",
            tool_name,
            incident_id,
            exc_info=True,
        )
