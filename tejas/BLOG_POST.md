# How I Built TEJAS: Real-Time Emergency Scene Intelligence with Gemini Live API, Imagen 3, and Google ADK

> **I created this for the purposes of entering the Gemini Live Agent Challenge hackathon.**
> `#GeminiLiveAgentChallenge`

---

## The Problem

When a first responder arrives at a multi-casualty incident — a highway pile-up, a hazmat spill, a structure fire — they face an overwhelming flood of information in the first 90 seconds. How many victims? What triage priority? What chemical is leaking and what's the safe standoff distance? Which hospital has trauma capacity right now?

Every second spent on radio calls and manual lookups is a second not spent saving lives.

I built **TEJAS** (Tactical Emergency Joint AI System) to give first responders a hands-free AI partner that sees what they see, hears what they say, and speaks actionable intelligence back in real time.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   First Responder Device                │
│  📷 Camera (JPEG frames)  🎙️ Microphone (PCM 16kHz)    │
└────────────────────┬────────────────────────────────────┘
                     │ WebSocket (bidirectional)
                     ▼
┌─────────────────────────────────────────────────────────┐
│                FastAPI Backend (Cloud Run)               │
│                                                         │
│  ┌──────────────────┐   ┌──────────────────────────┐   │
│  │  /ws/stream      │   │  /ws/adk                 │   │
│  │  (GenAI SDK      │   │  (Google ADK LlmAgent    │   │
│  │   bidi-stream)   │   │   + LiveRequestQueue)    │   │
│  └────────┬─────────┘   └────────────┬─────────────┘   │
│           └──────────────────────────┘                  │
│                         │                               │
│                         ▼                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │                Gemini 2.0 Flash Live              │  │
│  │   - Processes audio + video simultaneously        │  │
│  │   - Issues function calls for grounding           │  │
│  │   - Speaks responses back via audio               │  │
│  └───────────────────────────────────────────────────┘  │
│                         │                               │
│              ┌──────────┼──────────────────┐            │
│              ▼          ▼                  ▼            │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐   │
│  │  log_victim  │  │ search_     │  │  generate_   │   │
│  │  dispatch_   │  │ hazmat_erg  │  │  scene_report│   │
│  │  emergency   │  │ get_medical │  │  (Imagen 3)  │   │
│  │  resources   │  │ _protocols  │  └──────────────┘   │
│  └──────┬───────┘  └─────┬───────┘                     │
│         │                │                              │
│         ▼                ▼                              │
│  ┌────────────────────────────┐  ┌────────────────────┐ │
│  │     Cloud Firestore        │  │   Cloud Storage    │ │
│  │  incidents · victims ·     │  │   Tactical scene   │ │
│  │  dispatches · tool_logs    │  │   images (Imagen)  │ │
│  └────────────────────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                     │ WebSocket (bidirectional)
                     ▼
┌─────────────────────────────────────────────────────────┐
│              React + TypeScript HUD                     │
│  Triage counts · Dispatches · Hazards · Scene map       │
└─────────────────────────────────────────────────────────┘
```

---

## The Core: Gemini Live API Bidi-Streaming

The heart of TEJAS is a **bidirectional WebSocket stream** between the browser and the Gemini 2.0 Flash Live model. This is what makes real-time multimodal conversation possible:

```python
# backend/app/stream_manager.py (simplified)
async with client.aio.live.connect(
    model=settings.gemini_model,
    config=build_live_config(),
) as session:
    # Four concurrent async tasks:
    # 1. audio_sender  — PCM chunks from mic → Gemini
    # 2. video_sender  — JPEG frames from camera → Gemini
    # 3. text_sender   — text messages from UI → Gemini
    # 4. receiver      — Gemini responses → WebSocket → browser
    await asyncio.gather(
        _send_audio(session, audio_queue),
        _send_video(session, video_queue),
        _send_text(session, text_queue),
        _receive(session, websocket),
    )
```

The model sees **both the live video feed and hears the responder's voice simultaneously**. This is true multimodal grounding — Gemini can describe what it sees in the camera, answer spoken questions, and issue tool calls, all without interrupting the audio stream.

---

## Six Grounding Tools — Zero Hallucinations

Emergency response is a zero-tolerance domain. A wrong hospital name or incorrect safe-distance recommendation can cost lives. That's why every factual claim Gemini makes goes through a **grounding tool** backed by authoritative data:

### 1. `log_incident` — Victim Triage Logging
```python
def log_incident(incident_id, victim_id, status, injuries="", treatment_given="",
                 location_description="", notes=""):
    """Log or update a victim using the START triage protocol."""
    # Creates or updates a Firestore victim record; the HUD updates in real time
```
Gemini calls this while visually scanning the scene. The HUD immediately updates with triage counts by priority (IMMEDIATE/DELAYED/MINOR/DECEASED).

### 2. `dispatch_resources` — Smart Resource Dispatch
```python
def dispatch_resources(incident_id, resource_type, severity, gps_lat, gps_lng, notes=""):
    """Dispatch ambulance, fire_truck, hazmat_unit, police, or helicopter."""
    # Creates a dispatch record in Firestore; returns dispatch_id + estimated ETA
```

### 3. `query_hazmat_database` — Emergency Response Guidebook Lookup
```python
def query_hazmat_database(incident_id, chemical_name="", un_number=""):
    """Search the USDOT Emergency Response Guidebook (ERG)."""
    # Returns: safe_distance_feet, ppe_required, fire_response, spill_response
```
The entire USDOT ERG is pre-loaded in `data/hazmat_erg.json`. No third-party network call — no hallucination possible.

### 4. `get_medical_protocol` — Protocol-Grounded Treatment
```python
def get_medical_protocol(incident_id, injury_type, severity_level):
    """Return evidence-based treatment protocols for emergencies."""
    # Backed by data/medical_protocols.json (AHA / Red Cross baseline)
```

### 5. `get_nearest_hospital` — Trauma Center Lookup
```python
def get_nearest_hospital(incident_id, gps_lat, gps_lng, specialty_needed="general"):
    """Find nearest hospital with required specialty using Google Maps Places API."""
    # Falls back to curated demo list when Maps key not configured
```

### 6. `generate_scene_report` — Imagen 3 Tactical Scene Maps *(new!)*
```python
def generate_scene_report(incident_id, scene_description, hazards_identified=None, victim_count=0):
    """Generate a tactical overhead scene map using Imagen 3."""
    prompt = build_tactical_prompt(scene_description, hazards_identified, victim_count)
    response = client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt=prompt,
        config=GenerateImagesConfig(number_of_images=1, aspect_ratio="16:9"),
    )
    image_bytes = response.generated_images[0].image.image_bytes
    return {
        "status": "generated",
        "image_b64": base64.b64encode(image_bytes).decode(),
        "mime_type": "image/jpeg",
    }
```

After Gemini has completed its full scene assessment, it calls `generate_scene_report` and says *"Generating tactical scene map now — it will appear on your screen."* The Imagen 3-generated overhead map is then streamed to the responder's HUD in real time.

This is the **GenMedia capability** the Gemini Live API challenge specifically highlights: combining live bidirectional conversation with image generation.

---

## Google ADK Integration

Beyond the raw GenAI SDK, TEJAS also supports the **Google Agent Development Kit (ADK)** bidi-streaming path via a second WebSocket endpoint `/ws/adk`:

```python
# backend/app/adk_runner.py (simplified)
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.live_request_queue import LiveRequestQueue

def build_adk_agent() -> LlmAgent:
    return LlmAgent(
        name="tejas",
        model=settings.gemini_model,
        instruction=SYSTEM_INSTRUCTION,
        tools=[FunctionTool(fn) for fn in ADK_TOOLS],
    )
```

The ADK `Runner` manages the `LiveRequestQueue`, session lifecycle, and tool routing. This gives TEJAS two streaming backends simultaneously:

| Endpoint | Backend | Stream Type |
|---|---|---|
| `/ws/stream` | GenAI SDK `client.aio.live` | Raw bidi-stream |
| `/ws/adk` | ADK `LlmAgent` + `Runner` | Managed agent stream |

---

## Proactive Scene Scanning

One of the most powerful features is **proactive vision scanning** — TEJAS doesn't wait to be asked. Every 30 seconds, the backend injects a silent prompt asking Gemini to reassess the scene:

```python
# In stream_manager.py
async def _proactive_scan_loop(self, session):
    while True:
        await asyncio.sleep(settings.proactive_scan_interval_seconds)
        await session.send(
            input=BidiGenerateContentClientContent(
                turns=[Content(role="user", parts=[
                    Part(text="[BACKGROUND SCAN] Silently assess current scene...")
                ])]
            )
        )
```

This means if a hazmat leak worsens or a new victim becomes visible in the camera feed, TEJAS alerts the responder without waiting for a voice trigger.

---

## Infrastructure: Cloud Run + Terraform

Deployment is fully automated via **Cloud Build** and **Terraform**:

```hcl
# terraform/main.tf (excerpt)
resource "google_cloud_run_v2_service" "backend" {
  name     = "tejas-backend"
  location = var.region
  template {
    containers {
      image = "gcr.io/${var.project_id}/tejas-backend:latest"
      env { name = "GEMINI_MODEL"; value = var.gemini_model }
      env { name = "FIRESTORE_DB"; value = var.firestore_database }
    }
  }
}
```

`gcloud builds submit` triggers the CI pipeline; Terraform manages all Google Cloud resources (Cloud Run services, Firestore, Cloud Storage, IAM) as code. One `terraform apply` and the entire stack is live.

---

## The Frontend: React HUD for First Responders

The frontend is a React + TypeScript app optimized for use in full-screen on a tablet mounted in the ambulance or fire truck:

```tsx
// frontend/src/components/IncidentHUD.tsx (excerpt)
{incidentState.sceneImages.length > 0 && (() => {
  const latest = incidentState.sceneImages[incidentState.sceneImages.length - 1];
  return (
    <section>
      <h3>🛰️ SCENE MAP</h3>
      <img
        src={`data:${latest.mimeType};base64,${latest.imageB64}`}
        alt="Imagen tactical scene map"
      />
      <span>Imagen 3</span>
    </section>
  );
})()}
```

The HUD shows:
- Live triage counts by color (RED/YELLOW/GREEN/BLACK per START protocol)
- Active dispatches with real ETA estimates
- Hazmat warnings with safe standoff distances
- Recent tool call activity log
- **Imagen 3-generated tactical overhead map** (streamed live from the backend)

---

## Key Learnings

**1. Bidirectional streaming is fundamentally different from request-response.** You can't think in HTTP terms. Four concurrent asyncio tasks running simultaneously took some rethinking, but the result is genuinely magical — the model can process video, hear speech, and respond in audio, all at the same time.

**2. Grounding is not optional for safety-critical applications.** Every tool returns only what's in the authoritative data file. The system prompt explicitly tells Gemini: "Never state distances, dosages, or resource ETAs unless returned by a tool."

**3. Imagen 3 via `client.models.generate_images()` is straightforward.** The same `google-genai` SDK used for Gemini Live also handles Imagen — no separate client needed.

**4. ADK abstracts a lot of boilerplate.** The `LlmAgent` + `Runner` + `LiveRequestQueue` pattern handles session management cleanly. Worth using if you're building multi-agent systems.

**5. Proactive scanning is underrated.** Emergency scenes are dynamic. Polling Gemini every 30 seconds with a silent background prompt catches state changes the responder might miss.

---

## What's Next

- Voice activation ("Hey Tejas") via WebSpeech API for truly hands-free operation
- Thermal camera integration for victim detection in low-visibility conditions
- Multi-responder coordination via shared Firestore incident state
- Imagen-generated incident report PDFs for post-incident review

---

## Try It / Read the Code

The full source code is on GitHub. The README contains step-by-step setup instructions for both local development and Cloud Run deployment.

**Stack**: Gemini 2.0 Flash Live · Google ADK · Imagen 3 · FastAPI · React + TypeScript · Cloud Run · Firestore · Cloud Build · Terraform

`#GeminiLiveAgentChallenge` `#GoogleCloud` `#GeminiAPI` `#AIforGood`

---

*Built with ❤️ for first responders everywhere.*
