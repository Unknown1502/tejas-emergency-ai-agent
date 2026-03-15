/**
 * React hook for managing the WebSocket connection to the Tejas backend.
 *
 * Provides connection lifecycle management, message routing, incident
 * state aggregation, and typed event handlers for the UI layer.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ConnectionStatus,
  IncidentState,
  SceneImage,
  ServerMessage,
  SessionMetrics,
  ToolCallInfo,
  Victim,
  DispatchRecord,
  HazmatInfo,
} from "../types";
import { WebSocketService } from "../services/websocket";

// ---------------------------------------------------------------------------
// Hook Return Type
// ---------------------------------------------------------------------------

export interface UseWebSocketReturn {
  /** Current connection status. */
  status: ConnectionStatus;
  /** Whether the connection is active. */
  isConnected: boolean;
  /** Aggregated incident state from all tool calls. */
  incidentState: IncidentState;
  /** Session metrics from heartbeat messages. */
  metrics: SessionMetrics | null;
  /** Last error message. */
  lastError: string | null;
  /** Open the WebSocket connection. */
  connect: () => void;
  /** Close the WebSocket connection. */
  disconnect: () => void;
  /** Send a base64 audio chunk. */
  sendAudio: (base64Pcm: string) => void;
  /** Send a base64 video frame. */
  sendVideo: (base64Jpeg: string) => void;
  /** Send text input. */
  sendText: (text: string) => void;
  /** Initialize the session with incident data. */
  initSession: (data: {
    incidentId?: string;
    gpsLat?: number;
    gpsLng?: number;
  }) => void;
  /** Callback for handling audio responses (set by useAudio). */
  onAudioResponse: React.MutableRefObject<((base64Pcm: string) => void) | null>;
}

// ---------------------------------------------------------------------------
// Initial State
// ---------------------------------------------------------------------------

const INITIAL_INCIDENT_STATE: IncidentState = {
  incidentId: null,
  victims: [],
  dispatches: [],
  hazards: [],
  toolCalls: [],
  transcripts: [],
  isActive: false,
  sceneImages: [],
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useWebSocket(wsUrl?: string): UseWebSocketReturn {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [incidentState, setIncidentState] = useState<IncidentState>(INITIAL_INCIDENT_STATE);
  const [metrics, setMetrics] = useState<SessionMetrics | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  // Ref to avoid re-creating the service on every render
  const serviceRef = useRef<WebSocketService | null>(null);
  // Ref for audio response callback (set by useAudio)
  const onAudioResponse = useRef<((base64Pcm: string) => void) | null>(null);

  // Initialize the service once
  useEffect(() => {
    const config = wsUrl ? { url: wsUrl } : undefined;
    serviceRef.current = new WebSocketService(config);

    const unsubStatus = serviceRef.current.onStatus((s) => setStatus(s));
    const unsubError = serviceRef.current.onError((e) => setLastError(e));
    const unsubMessage = serviceRef.current.onMessage((msg) =>
      handleServerMessage(msg)
    );

    return () => {
      unsubStatus();
      unsubError();
      unsubMessage();
      serviceRef.current?.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsUrl]);

  // ------------------------------------------------------------------
  // Message Routing
  // ------------------------------------------------------------------

  const handleServerMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case "audio":
        handleAudioMessage(msg);
        break;
      case "transcript":
        handleTranscriptMessage(msg);
        break;
      case "tool_call":
        handleToolCallMessage(msg);
        break;
      case "tool_result":
        handleToolResultMessage(msg);
        break;
      case "status":
        handleStatusMessage(msg);
        break;
      case "heartbeat":
        handleHeartbeatMessage(msg);
        break;
      case "error":
        handleErrorMessage(msg);
        break;
      case "turn_complete":
        // Could trigger UI state changes
        break;
      case "scene_image":
        handleSceneImageMessage(msg);
        break;
      default:
        break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAudioMessage = useCallback((msg: ServerMessage) => {
    const audioData = msg.data as string;
    if (audioData && onAudioResponse.current) {
      onAudioResponse.current(audioData);
    }
  }, []);

  const handleTranscriptMessage = useCallback((msg: ServerMessage) => {
    const text = msg.data as string;
    if (text) {
      setIncidentState((prev) => ({
        ...prev,
        transcripts: [...prev.transcripts, text],
      }));
    }
  }, []);

  const handleToolCallMessage = useCallback((msg: ServerMessage) => {
    const data = msg.data as ToolCallInfo;
    if (data) {
      const toolCall: ToolCallInfo = {
        name: data.name,
        args: data.args,
        status: "executing",
        timestamp: Date.now(),
      };
      setIncidentState((prev) => ({
        ...prev,
        toolCalls: [...prev.toolCalls, toolCall],
      }));
    }
  }, []);

  const handleToolResultMessage = useCallback((msg: ServerMessage) => {
    const data = msg.data as {
      name: string;
      result: Record<string, unknown>;
      status: string;
    };
    if (!data) return;

    // Update the most recent matching tool call with the result
    setIncidentState((prev) => {
      const updatedToolCalls = [...prev.toolCalls];
      for (let i = updatedToolCalls.length - 1; i >= 0; i--) {
        const tc = updatedToolCalls[i];
        if (tc && tc.name === data.name && tc.status === "executing") {
          updatedToolCalls[i] = { ...tc, result: data.result, status: "completed" };
          break;
        }
      }

      // Extract domain entities from tool results
      const updates = extractIncidentUpdates(data.name, data.result, prev);

      return {
        ...prev,
        ...updates,
        toolCalls: updatedToolCalls,
        isActive: true,
      };
    });
  }, []);

  const handleStatusMessage = useCallback((msg: ServerMessage) => {
    const data = msg.data as { status: string; message: string };
    if (data?.status === "session_initialized") {
      setIncidentState((prev) => ({
        ...prev,
        isActive: true,
      }));
    }
  }, []);

  const handleHeartbeatMessage = useCallback((msg: ServerMessage) => {
    const data = msg.data as {
      session_id: string;
      uptime_seconds: number;
      audio_chunks_sent: number;
      audio_chunks_received: number;
      video_frames_sent: number;
      tool_calls_executed: number;
    };
    if (data) {
      setMetrics({
        sessionId: data.session_id,
        uptimeSeconds: data.uptime_seconds,
        audioChunksSent: data.audio_chunks_sent,
        audioChunksReceived: data.audio_chunks_received,
        videoFramesSent: data.video_frames_sent,
        toolCallsExecuted: data.tool_calls_executed,
      });
    }
  }, []);

  const handleErrorMessage = useCallback((msg: ServerMessage) => {
    const data = msg.data as { message: string };
    if (data?.message) {
      setLastError(data.message);
    }
  }, []);

  /**
   * GenMedia: Handle Imagen 3 scene image broadcast from the backend.
   * The backend sends this after generate_scene_report returns image_b64.
   */
  const handleSceneImageMessage = useCallback((msg: ServerMessage) => {
    const data = msg.data as {
      image_b64: string;
      mime_type: string;
      scene_description: string;
      victim_count: number;
      hazards: string[];
      incident_id: string | null;
    };
    if (!data?.image_b64) return;
    const sceneImage: SceneImage = {
      imageB64: data.image_b64,
      mimeType: data.mime_type ?? "image/jpeg",
      sceneDescription: data.scene_description ?? "",
      victimCount: data.victim_count ?? 0,
      hazards: data.hazards ?? [],
      incidentId: data.incident_id ?? null,
      timestamp: Date.now(),
    };
    setIncidentState((prev) => ({
      ...prev,
      sceneImages: [...prev.sceneImages, sceneImage],
    }));
  }, []);

  // ------------------------------------------------------------------
  // Domain Entity Extraction
  // ------------------------------------------------------------------

  function extractIncidentUpdates(
    toolName: string,
    result: Record<string, unknown>,
    prev: IncidentState
  ): Partial<IncidentState> {
    switch (toolName) {
      case "log_incident": {
        const victim: Victim = {
          victimId: result.victim_id as string,
          status: result.victim_status as Victim["status"],
          injuries: result.injuries as string | undefined,
          treatmentGiven: result.treatment_given as string | undefined,
          locationDescription: result.location_description as string | undefined,
          notes: result.notes as string | undefined,
          timestamp: Date.now(),
        };
        // Update existing victim or add new
        const existing = prev.victims.findIndex(
          (v) => v.victimId === victim.victimId
        );
        const updatedVictims = [...prev.victims];
        if (existing >= 0) {
          updatedVictims[existing] = victim;
        } else {
          updatedVictims.push(victim);
        }
        return { victims: updatedVictims };
      }

      case "dispatch_resources": {
        const dispatch: DispatchRecord = {
          dispatchId: result.dispatch_id as string,
          resourceType: result.resource_type as DispatchRecord["resourceType"],
          severity: result.severity as DispatchRecord["severity"],
          etaMinutes: result.estimated_eta_minutes as number,
          status: result.status as string,
          notes: result.notes as string | undefined,
          timestamp: Date.now(),
        };
        return { dispatches: [...prev.dispatches, dispatch] };
      }

      case "query_hazmat_database": {
        const hazmat: HazmatInfo = {
          chemicalName: result.chemical_name as string,
          unNumber: result.un_number as string | undefined,
          hazardClass: result.hazard_class as string | undefined,
          safeDistanceFt: result.safe_distance_ft as number,
          ppeRequired: (result.ppe_required as string[]) ?? [],
          immediateActions: (result.immediate_actions as string[]) ?? [],
        };
        // Avoid duplicate hazards
        const existingHazard = prev.hazards.find(
          (h) => h.chemicalName === hazmat.chemicalName
        );
        if (existingHazard) return {};
        return { hazards: [...prev.hazards, hazmat] };
      }

      default:
        return {};
    }
  }

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  const connect = useCallback(() => {
    setLastError(null);
    serviceRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    serviceRef.current?.disconnect();
    setIncidentState(INITIAL_INCIDENT_STATE);
    setMetrics(null);
  }, []);

  const sendAudio = useCallback((base64Pcm: string) => {
    serviceRef.current?.sendAudio(base64Pcm);
  }, []);

  const sendVideo = useCallback((base64Jpeg: string) => {
    serviceRef.current?.sendVideo(base64Jpeg);
  }, []);

  const sendText = useCallback((text: string) => {
    serviceRef.current?.sendText(text);
  }, []);

  const initSession = useCallback(
    (data: { incidentId?: string; gpsLat?: number; gpsLng?: number }) => {
      serviceRef.current?.sendSessionInit(data);
      if (data.incidentId) {
        setIncidentState((prev) => ({
          ...prev,
          incidentId: data.incidentId ?? null,
        }));
      }
    },
    []
  );

  return {
    status,
    isConnected: status === "connected",
    incidentState,
    metrics,
    lastError,
    connect,
    disconnect,
    sendAudio,
    sendVideo,
    sendText,
    initSession,
    onAudioResponse,
  };
}
