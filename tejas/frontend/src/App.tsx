/**
 * Root application component for the Tejas frontend.
 *
 * Orchestrates all hooks and components:
 * - useWebSocket: manages server connection and incident state
 * - useCamera: manages camera stream and frame capture
 * - useAudio: manages microphone capture and audio playback
 * - useGeolocation: provides GPS coordinates
 *
 * The App serves as the top-level coordinator. When the user taps
 * "Start", it:
 * 1. Connects the WebSocket
 * 2. Starts the camera and frame capture
 * 3. Starts the microphone and audio capture
 * 4. Sends session init with GPS coordinates
 * 5. Wires audio responses from server to the audio player
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { useCamera } from "./hooks/useCamera";
import { useAudio } from "./hooks/useAudio";
import { useGeolocation } from "./hooks/useGeolocation";
import { CameraView } from "./components/CameraView";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { IncidentHUD } from "./components/IncidentHUD";
import { ControlPanel } from "./components/ControlPanel";
import { SceneHeader } from "./components/SceneHeader";

const App: React.FC = () => {
  const ws = useWebSocket();
  const camera = useCamera();
  const audio = useAudio();
  const geo = useGeolocation();

  const sessionActiveRef = useRef(false);
  const [activeIncidentId, setActiveIncidentId] = useState<string | null>(null);

  // ------------------------------------------------------------------
  // Wire audio playback to WebSocket audio responses
  // ------------------------------------------------------------------

  useEffect(() => {
    ws.onAudioResponse.current = (base64Pcm: string) => {
      audio.playAudio(base64Pcm);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audio.playAudio]);

  // ------------------------------------------------------------------
  // Request geolocation on mount
  // ------------------------------------------------------------------

  useEffect(() => {
    geo.requestLocation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------------
  // Session lifecycle
  // ------------------------------------------------------------------

  const handleStartSession = useCallback(async () => {
    if (sessionActiveRef.current) return;
    sessionActiveRef.current = true;

    // 1. Connect WebSocket
    ws.connect();

    // 2. Start camera with frame forwarding
    await camera.start((base64Jpeg) => {
      ws.sendVideo(base64Jpeg);
    });

    // 3. Start microphone with audio forwarding
    await audio.startCapture((base64Pcm) => {
      ws.sendAudio(base64Pcm);
    });

    // 4. Initialize session with GPS once connected
    // Small delay to allow WebSocket to fully connect
    setTimeout(() => {
      const incidentId = `INC-${Date.now().toString(36).toUpperCase()}`;
      setActiveIncidentId(incidentId);
      ws.initSession({
        incidentId,
        gpsLat: geo.location?.latitude,
        gpsLng: geo.location?.longitude,
      });
    }, 1000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo.location]);

  const handleStopSession = useCallback(() => {
    sessionActiveRef.current = false;
    setActiveIncidentId(null);
    audio.stopCapture();
    audio.stopPlayback();
    camera.stop();
    ws.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div style={styles.root}>
      {/* Full-viewport camera feed */}
      <CameraView
        videoRef={camera.videoRef}
        isActive={camera.isActive}
        facingMode={camera.facingMode}
      />

      {/* Top command bar — always visible */}
      <SceneHeader
        incidentId={activeIncidentId}
        gpsLat={geo.location?.latitude ?? null}
        gpsLng={geo.location?.longitude ?? null}
        isActive={ws.status === "connected"}
      />

      {/* Connection status badge — bottom-left */}
      <ConnectionStatus
        status={ws.status}
        metrics={ws.metrics}
        lastError={ws.lastError}
      />

      {/* Incident HUD overlay */}
      <IncidentHUD incidentState={ws.incidentState} />

      {/* Bottom control panel */}
      <ControlPanel
        connectionStatus={ws.status}
        isCapturing={audio.isCapturing}
        isMuted={audio.isMuted}
        isCameraActive={camera.isActive}
        onStartSession={handleStartSession}
        onStopSession={handleStopSession}
        onToggleMute={audio.toggleMute}
        onToggleCamera={camera.toggleCamera}
      />

      {/* Error overlay */}
      {(camera.error || audio.error || geo.error) && (
        <div style={styles.errorBanner}>
          {camera.error || audio.error || geo.error}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles: Record<string, React.CSSProperties> = {
  root: {
    position: "relative",
    width: "100vw",
    height: "100vh",
    overflow: "hidden",
    backgroundColor: "#0a0a1a",
    fontFamily: "'Inter', 'SF Pro', -apple-system, sans-serif",
    color: "#eee",
    userSelect: "none",
    WebkitUserSelect: "none",
  },
  errorBanner: {
    position: "fixed",
    top: "60px",
    left: "50%",
    transform: "translateX(-50%)",
    zIndex: 200,
    padding: "10px 20px",
    borderRadius: "8px",
    backgroundColor: "rgba(239, 68, 68, 0.9)",
    color: "#fff",
    fontSize: "13px",
    fontWeight: 500,
    maxWidth: "90%",
    textAlign: "center" as const,
    boxShadow: "0 4px 12px rgba(239, 68, 68, 0.3)",
  },
};

export default App;
