"""
Gemini Live API agent configuration for the Tejas application.

Defines the system instruction, tool declarations, and session
configuration for the Gemini 2.0 Flash Live API. This module
encapsulates all Gemini-specific setup so the stream manager
can focus purely on WebSocket/stream orchestration.
"""

from __future__ import annotations

import logging
from typing import Optional

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System Instruction
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTION = """You are Tejas, an emergency scene intelligence agent. Your persona is "Commander" -- calm, authoritative, and decisive. You never panic. You never hesitate. You speak with the steady confidence of a veteran incident commander who has managed hundreds of emergencies.

IDENTITY:
- Your name is Tejas. If asked, say "I am Tejas, your emergency scene intelligence agent."
- You are a decision-support tool, not a replacement for professional emergency services.
- You always include the disclaimer when giving medical or hazmat guidance: "This is protocol-based guidance. Professional evaluation is required."

CORE BEHAVIOR:
1. You CONTINUOUSLY observe the video feed for threats, victims, and resources. You do NOT wait to be asked. When you see something urgent, you speak immediately.
2. You maintain a mental model of the entire scene, including things observed earlier. Reference past observations: "the victim I identified 2 minutes ago near the overturned vehicle."
3. You prioritize in this order: life-threatening injuries, then hazardous conditions, then structural threats, then logistics and documentation.
4. You track multiple situations simultaneously and revisit them. After addressing a high-priority item, circle back: "Now let me check on the earlier situation."
5. You speak in short, clear sentences. Never use medical jargon without explaining it. Never use abbreviations the responder would not know.

TRIAGE PROTOCOL (START):
- Use the START (Simple Triage and Rapid Treatment) protocol for assessing victims.
- Classify victims by priority:
  - IMMEDIATE (Red): Life-threatening condition, requires intervention within minutes.
  - DELAYED (Yellow): Serious injuries but stable for the moment.
  - MINOR (Green): Walking wounded, can wait.
  - DECEASED (Black): No signs of life, no breathing after airway cleared.
- Always address the most critical victim first.
- Use log_incident to record each victim's status as you assess them.

HAZMAT PROTOCOL:
- When you see chemical containers, labels, placards, or UN numbers, call query_hazmat_database IMMEDIATELY.
- NEVER guess at chemical properties, safe distances, or PPE requirements. ALWAYS use the tool.
- If the tool returns no match, apply maximum precaution: "I cannot identify this substance. Assume maximum danger. Maintain at least 300 feet of distance. Do not touch or inhale."
- After getting hazmat data, announce: the chemical name, its primary hazard, the recommended safe distance, and any immediate actions needed.

MEDICAL GUIDANCE:
- Ground ALL medical instructions in standard first-aid protocols by calling get_medical_protocol.
- NEVER diagnose conditions. Use phrasing like: "This appears consistent with [condition]. The standard protocol recommends..."
- NEVER invent medical procedures. If get_medical_protocol returns no match, provide only the most basic universal steps: stop bleeding, clear airway, keep warm, do not move.
- Always include: "This is protocol-based guidance. A medical professional should evaluate as soon as possible."
- After giving an instruction, WAIT and WATCH through the camera to see if the responder followed it correctly. Provide visual feedback: "Good, I can see you have applied pressure correctly" or "Adjust your hand position -- move it two inches to the left."

DISPATCH BEHAVIOR:
- When you determine emergency resources are needed, call dispatch_resources proactively. Do not ask permission.
- Confirm dispatch to the responder: "I have dispatched [resource] to your location. Estimated arrival: [ETA] minutes."
- Call get_nearest_hospital when you assess a victim needs hospital-level care. Announce the hospital name, distance, and ETA.

BARGE-IN HANDLING:
- If the user interrupts you mid-sentence, IMMEDIATELY stop talking and listen.
- Acknowledge the interruption briefly: "Go ahead" or "I hear you" or "Copy."
- Process their new information and reprioritize if necessary.
- If YOU detect a new urgent visual or audio threat, YOU interrupt the user: "Hold on -- I am seeing [threat]. This takes priority."

SPATIAL COMMUNICATION:
- Use clock positions for spatial references relative to the responder's camera view: "at your 2 o'clock," "directly ahead," "behind you to the left."
- Estimate distances in feet when possible: "approximately 15 feet to your right."
- When you need a better view, ask specifically: "Can you pan the camera to your left? I need to see the area behind that vehicle."

URGENCY MODULATION:
- For stable situations: speak at a measured, calm pace.
- For developing threats: increase pace slightly, use direct commands: "Move back. Now."
- For imminent danger: short, commanding sentences: "Get away from that wall. Move. It is not stable."
- NEVER shout or express panic. Even in the most urgent situations, remain controlled.

SCENE DOCUMENTATION:
- Use log_incident to record every victim you identify, with their status and location.
- When the situation stabilizes, summarize: "Let me compile what I have observed. Total victims: [N]. Condition summary: [details]. Hazards identified: [list]. Resources dispatched: [list]. Nearest trauma center: [name, distance]."
- This summary serves as the EMS handoff report.

SCENE DOCUMENTATION WITH IMAGEN (GENAI MEDIA GENERATION):
- After completing a full initial scene assessment (victims triaged, hazards identified, resources dispatched), call generate_scene_report.
- Provide a detailed spatial description of the scene: positions of victims by clock direction, hazard zones, fire spread direction, staging areas for incoming units.
- Announce to the responder: "Generating tactical scene map now. It will appear on your screen."
- This creates a Google Imagen-generated overhead view of the incident for incident command briefings and EMS handoff.
- Only call this once per scene assessment cycle. Do not call it for minor updates.

GROUNDING RULES (CRITICAL -- DO NOT VIOLATE):
1. NEVER hallucinate chemical data. Always call query_hazmat_database.
2. NEVER invent medical protocols. Always call get_medical_protocol.
3. NEVER fabricate hospital names or locations. Always call get_nearest_hospital.
4. If you cannot clearly see something in the video feed, say: "I cannot clearly make out [X]. Can you move closer or adjust the angle?"
5. If you are uncertain about a threat assessment, say: "I am not certain, but this could be [X]. Let us treat it as [severity] until confirmed."
6. NEVER provide specific drug dosages or medication recommendations.
7. NEVER tell a responder to enter a structurally compromised building.
"""


# ---------------------------------------------------------------------------
# Tool Declarations
# ---------------------------------------------------------------------------

def build_tool_declarations() -> list[types.Tool]:
    """
    Build the Gemini function calling tool declarations.

    Each declaration maps to a handler in app.tools. The schemas
    define the parameter types and descriptions that Gemini uses
    to decide when and how to invoke each tool.
    """
    return [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="dispatch_resources",
                description=(
                    "Dispatch emergency resources (ambulance, fire truck, hazmat unit, "
                    "police, or helicopter) to the incident scene. Call this proactively "
                    "when you determine resources are needed based on scene assessment."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "resource_type": types.Schema(
                            type="STRING",
                            enum=["ambulance", "fire_truck", "hazmat_unit", "police", "helicopter"],
                            description="Type of emergency resource to dispatch.",
                        ),
                        "severity": types.Schema(
                            type="STRING",
                            enum=["critical", "urgent", "moderate"],
                            description="Severity level determining dispatch priority and ETA.",
                        ),
                        "gps_lat": types.Schema(
                            type="NUMBER",
                            description="Latitude of the dispatch destination.",
                        ),
                        "gps_lng": types.Schema(
                            type="NUMBER",
                            description="Longitude of the dispatch destination.",
                        ),
                        "notes": types.Schema(
                            type="STRING",
                            description="Additional context for the dispatch crew.",
                        ),
                    },
                    required=["resource_type", "severity", "gps_lat", "gps_lng"],
                ),
            ),
            types.FunctionDeclaration(
                name="query_hazmat_database",
                description=(
                    "Look up hazardous material safety data by chemical name or UN number. "
                    "MUST be called whenever a chemical container, hazmat label, placard, "
                    "or UN number is observed. Returns safe distances, PPE requirements, "
                    "and response procedures from the USDOT Emergency Response Guidebook."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "chemical_name": types.Schema(
                            type="STRING",
                            description="Common name of the chemical (e.g., 'gasoline', 'chlorine').",
                        ),
                        "un_number": types.Schema(
                            type="STRING",
                            description="UN identification number (e.g., 'UN1203', '1203').",
                        ),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="log_incident",
                description=(
                    "Log or update a victim's status in the incident record. Call this "
                    "for every victim identified to maintain a complete scene record. "
                    "Also used to update victim status as treatment progresses."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "victim_id": types.Schema(
                            type="STRING",
                            description=(
                                "Descriptive identifier for the victim "
                                "(e.g., 'victim_1', 'person_near_car', 'child_by_door')."
                            ),
                        ),
                        "status": types.Schema(
                            type="STRING",
                            enum=["immediate", "delayed", "minor", "deceased", "unknown"],
                            description="START triage classification for the victim.",
                        ),
                        "injuries": types.Schema(
                            type="STRING",
                            description="Description of observed injuries.",
                        ),
                        "treatment_given": types.Schema(
                            type="STRING",
                            description="Description of any treatment administered so far.",
                        ),
                        "location_description": types.Schema(
                            type="STRING",
                            description="Where the victim is located relative to the scene.",
                        ),
                        "notes": types.Schema(
                            type="STRING",
                            description="Additional observations about the victim.",
                        ),
                    },
                    required=["victim_id", "status"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_medical_protocol",
                description=(
                    "Retrieve a standard first-aid protocol for a specific injury type "
                    "and severity level. Returns step-by-step instructions grounded in "
                    "AHA and Red Cross guidelines. MUST be called before giving any "
                    "medical treatment instructions."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "injury_type": types.Schema(
                            type="STRING",
                            description=(
                                "Type of injury (e.g., 'hemorrhage', 'fracture', 'burn', "
                                "'cardiac_arrest', 'choking', 'concussion', 'laceration', "
                                "'sprain', 'hypothermia', 'heat_stroke')."
                            ),
                        ),
                        "severity_level": types.Schema(
                            type="STRING",
                            enum=["minor", "moderate", "severe", "life_threatening"],
                            description="Severity of the injury.",
                        ),
                    },
                    required=["injury_type", "severity_level"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_nearest_hospital",
                description=(
                    "Find the nearest hospital with the required specialty capability. "
                    "Returns hospital name, address, distance, ETA, and contact info. "
                    "Call when a victim needs hospital-level care."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "gps_lat": types.Schema(
                            type="NUMBER",
                            description="Latitude of the incident location.",
                        ),
                        "gps_lng": types.Schema(
                            type="NUMBER",
                            description="Longitude of the incident location.",
                        ),
                        "specialty_needed": types.Schema(
                            type="STRING",
                            enum=["trauma", "burn", "pediatric", "general", "cardiac"],
                            description="Hospital specialty required for the patient.",
                        ),
                    },
                    required=["gps_lat", "gps_lng"],
                ),
            ),
            types.FunctionDeclaration(
                name="generate_scene_report",
                description=(
                    "Generate a tactical overhead scene map image using Google Imagen 3 (GenAI Media). "
                    "Call after the initial scene assessment is complete — when you have identified "
                    "major victims, hazards, and dispatched resources. Provide a detailed spatial "
                    "description of the scene. The generated image appears on the responder's HUD "
                    "and serves as the incident command briefing document and EMS handoff reference."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "scene_description": types.Schema(
                            type="STRING",
                            description=(
                                "Detailed spatial description of the scene for Imagen. "
                                "Include: overall layout, victim positions using clock directions "
                                "(e.g. 'victim at 3 o'clock, 20 feet'), hazard zones, fire spread "
                                "direction, chemical perimeter, staging area for incoming units, "
                                "road orientation, and any notable landmarks or structures."
                            ),
                        ),
                        "hazards_identified": types.Schema(
                            type="ARRAY",
                            items=types.Schema(type="STRING"),
                            description=(
                                "List of identified hazards, e.g. "
                                "['UN1203 gasoline tanker at 9 o'clock', 'building fire at 12 o'clock']."
                            ),
                        ),
                        "victim_count": types.Schema(
                            type="INTEGER",
                            description="Total number of victims identified on the scene.",
                        ),
                    },
                    required=["scene_description"],
                ),
            ),
        ])
    ]


# ---------------------------------------------------------------------------
# Session Configuration
# ---------------------------------------------------------------------------

def build_live_config() -> types.LiveConnectConfig:
    """
    Build the configuration for a Gemini Live API bidirectional session.

    Configures:
    - Audio-only response modality (voice output)
    - Voice selection (Orus: deep, authoritative)
    - System instruction (emergency commander persona)
    - Tool declarations (5 emergency response tools)
    """
    settings = get_settings()
    tools = build_tool_declarations()

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=settings.voice_name,
                )
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part(text=SYSTEM_INSTRUCTION)]
        ),
        tools=tools,
    )

    logger.info(
        "Built Live API config: model=%s, voice=%s, tools=%d",
        settings.gemini_model,
        settings.voice_name,
        sum(len(t.function_declarations) for t in tools),
    )
    return config


# ---------------------------------------------------------------------------
# Client Factory
# ---------------------------------------------------------------------------

_client: Optional[genai.Client] = None


def get_genai_client() -> genai.Client:
    """
    Return a singleton Google GenAI client.

    Uses Vertex AI authentication by default (recommended for Cloud Run
    deployment). Falls back to API key authentication if configured.
    """
    global _client
    if _client is not None:
        return _client

    settings = get_settings()

    if settings.use_vertex_ai and settings.gcp_project_id:
        _client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_region,
        )
        logger.info(
            "GenAI client initialized with Vertex AI: project=%s, region=%s",
            settings.gcp_project_id,
            settings.gcp_region,
        )
    elif settings.gemini_api_key:
        # Use v1alpha for the Live API (bidiGenerateContent) — the stable
        # gemini-2.0-flash-live-001 and flash-exp models are served on
        # v1alpha for bidi streaming; v1beta returns 1008 "not found".
        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options={"api_version": "v1alpha"},
        )
        logger.info("GenAI client initialized with API key (v1alpha)")
    else:
        # Attempt default credentials
        _client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id or "tejas-project",
            location=settings.gcp_region,
        )
        logger.warning(
            "GenAI client initialized with default credentials. "
            "Set GCP_PROJECT_ID or GEMINI_API_KEY for explicit auth."
        )

    return _client
