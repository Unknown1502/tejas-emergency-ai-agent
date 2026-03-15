# Tejas Submission Video Script (3:55s target)

## Scene 1: The Problem & Solution (0:00 - 0:45)
**Visual:** 
Start with a split screen. On the left: a frantic, crowded emergency scene (stock footage or the 3D demo). On the right: a first responder trying to hold a phone, type, and stop bleeding. Big red X. Text: "Too much cognitive load."
Transition to the `tejas/demo/index.html` main HUD page.

**Audio (Voiceover):**
> "In an emergency, a first responder has one set of hands and zero free attention. Typing into a chatbot gets people killed. Meet Tejas. Built for the Google Gemini Live Agent Challenge. Tejas is an AI Incident Commander that watches, thinks, and acts—completely hands-free."

## Scene 2: The Core Tech - Live Vision & Interruption (0:45 - 2:00)
**Visual:** 
Record a live run-through of the actual `tejas/frontend` React app using a webcam feed pointed at a printed UN 1017 Hazmat placard. 
Have a terminal window visible in the corner showing the `FastAPI` server outputting `ws` binary streams and `tool_call` executions in real-time.

**Audio (Live Demo Capture / Voiceover):**
> "Let’s see it live, powered by the Gemini 2.5 Flash Native Audio Live API on Google Cloud Run."
> Start the app. Point camera at a UN 1017 placard.
> **AI Audio (from app):** "Hold on. UN 1017. That is Chlorine gas. Back away."
> **Voiceover:** "Notice, I didn't say a word. The Gemini Live API analyzed the 2fps Canvas video stream over WebSockets, recognized the threat, and interrupted the silence."
> Next, start talking over the AI. 
> **You:** "Tejas, I also have a conscious victim with an arterial bleed."
> **Voiceover:** "Our client-side Voice Activity Detector instantly cuts the playback buffer for true, low-latency barge-in."

## Scene 3: Grounding & Tools (Zero Hallucination) (2:00 - 2:45)
**Visual:** 
Screen record the Google Cloud Console. Show the Firestore Database where the incident is being logged. Show the `tejas/backend/app/tools.py` code briefly.

**Audio (Voiceover):**
> "In life-or-death scenarios, LLMs cannot hallucinate. Tejas uses function calling to ground every decision. When it saw the Chlorine gas, Gemini didn't guess the distance. It called `query_hazmat_database` and pulled from the DOT Emergency Response Guidebook. It called `dispatch_resources` and logged the GPS coordinates directly to Firestore. We use 6 distinct tools for medical protocols, hospital routing, and mapping."

## Scene 4: The Bonus / Infrastructure (2:45 - 3:20)
**Visual:** 
Show the `tejas/terraform/main.tf` file and a quick terminal showing `terraform apply` completing. Show the Imagen 3 generated overhead map.

**Audio (Voiceover):**
> "To give arriving commanders instant context, Tejas uses Google Imagen 3 to generate tactical overhead scene maps. And the entire infrastructure—FastAPI WebSockets, Cloud Run, Firestore, and Secret Manager—is deployed as code via Terraform."

## Scene 5: Conclusion (3:20 - 3:55)
**Visual:**
Show the architecture diagram from the demo page. Fade back to the Tejas logo. Text: "Tejas: See. Analyze. Act." 

**Audio (Voiceover):**
> "Tejas proves we can move beyond the text box to build agents that save lives. Thank you to the Google team for the Gemini Live API. Let's build the future of emergency response."
