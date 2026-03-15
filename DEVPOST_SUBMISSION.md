## Required Devpost Fields

**Project Name:** Tejas — AI Incident Commander
**Tagline:** Built on Gemini 2.5 Flash Live API. A hands-free, eyes-up incident commander that watches, thinks, and acts for first responders in real-time.
**Tracks:** Live Agents, Machine Learning/AI

---

## Story (The Main Description)

### The Problem
Every year, preventable deaths occur at emergency scenes because first responders face an impossible cognitive load:
- **One set of hands** — occupied with the patient
- **One pair of eyes** — focused on the immediate victim
- **Zero free attention** — to reference hazmat data, verify protocols, or coordinate resources.

Current tools rely on the "text box paradigm." They require a responder to stop treating a patient, pick up a radio or phone, type a query, and read a screen. In a multi-casualty incident with a hazardous leak, that 30-second gap is the difference between life and death. 

### What it does: Breaking the Text Box
**Tejas** *(Sanskrit: "radiance, light in the dark")* is a next-generation AI Incident Commander built to win the **Live Agents** category. Tejas is not a chatbot you talk to. It is an agent that watches, thinks, and acts—without waiting to be asked.

Using the **Gemini 2.5 Flash Native Audio Live API**, Tejas streams 2-5fps video frames and 16kHz PCM audio bidirectionally via WebSockets. 

**Proactive Vision:** The moment a responder's camera spots a UN Hazmat placard (e.g., UN 1017 Chlorine), Tejas identifies it *before the responder speaks a word*, queries the DOT Emergency Response Guidebook via function calling, and instantly speaks a warning to evacuate upwind. 

### How we built it (Architecture & Cloud Deployment)
**The Backend (Google Cloud Run + FastAPI):**
We utilize a FastAPI backend deployed on **Google Cloud Run** with session affinity. A custom `Stream Manager` orchestrates three concurrent async tasks per WebSocket: client ingestion, Gemini bidi-routing, and Firestore tool execution.

**The SDK:** 
Powered by the official `google-genai` Python SDK utilizing `BidiGenerateContent`. 

**The Frontend:** 
A purpose-built React/Vite PWA intended for a drone feed or responder head-cam. Crucially, it features a **client-side Voice Activity Detector (VAD)**. First responders operate in chaotic environments. If Tejas is speaking a medical protocol and the responder yells *"Victim is coding!"*, our VAD cuts the audio buffer within 50ms (achieving true barge-in), and immediately prioritizes the new audio stream.

### Grounding & Zero Hallucination (Tools used)
In life-and-death scenarios, an LLM *cannot* hallucinate distances or medical protocols. Every factual action Tejas takes is executed via a Cloud Firestore grounded tool:
1. `query_hazmat_database`: USDOT ERG rules.
2. `get_medical_protocol`: AHA First-aid standards.
3. `dispatch_resources`: Firestore logging with GPS coordinates.
4. `get_nearest_hospital`: Google Places API routing for Trauma/Burn centers.
5. `log_incident`: Live persistent scene documentation.
6. `generate_scene_report`: Generates tactical overhead maps via **Google Imagen 3**.

### Challenges we ran into
Handling raw PCM16 audio chunks over a single WebSocket alongside base64 JPEG Canvas frames was incredibly complex. The Gemini Live API requires strict formatting. Additionally, ensuring the AI didn't just "talk over" the frantic user required us to build our own client-side VAD chunk-analyzer to trigger the "interrupt/barge-in" sequence perfectly, signaling the backend to clear the current generation queue.

### Accomplishments that we're proud of
We fully modeled the infrastructure as code. The entire GCP stack (Cloud Run, Artifact Registry, Secret Manager, Firestore) is spun up via a single `terraform apply`. We successfully moved beyond the text box, creating a scenario where the AI genuinely feels like a veteran commander in the responder's earpiece.

### What we learned
Building with Gemini Live fundamentally shifted how we view UI. We learned that the best user interface for an emergency is *no user interface*. The latency of the Flash model allowed us to build an application entirely governed by speech and passive vision.

### What's next for Tejas
We plan to deploy Tejas onto smart-glasses (like Ray-Ban Meta or Vuzix), shifting the camera feed from the mobile phone directly to the responder's eye-line, making it 100% hands-free and operational in live-fire paramedic environments.

---

## 📸 Additional Uploads Checklist (Don't forget these!)
- [ ] Upload the `.png` Architecture Diagram generated in the README.
- [ ] Add the Youtube/Vimeo link to the 4-minute Submission Video.
- [ ] Add the link to the public GitHub repository.

---

## Bonus Points Claimed
✅ **Automated Cloud Deployment:** Full Terraform scripts provided in the `terraform/` directory.
✅ **Publish Content:** Blog post published regarding the architecture of building Gemini Live bidi-streaming over FastApi. (Link to be added).