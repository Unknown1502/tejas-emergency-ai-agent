/**
 * ControlPanel component for the Tejas frontend.
 *
 * Fixed bottom toolbar providing controls for:
 * - Starting/stopping the session (connect + camera + mic)
 * - Muting/unmuting the microphone
 * - Toggling the camera facing direction
 * - Text input fallback
 *
 * Designed as a floating toolbar with glass-morphism styling.
 */

import React from "react";
import type { ConnectionStatus } from "../types";

interface ControlPanelProps {
  connectionStatus: ConnectionStatus;
  isCapturing: boolean;
  isMuted: boolean;
  isCameraActive: boolean;
  onStartSession: () => void;
  onStopSession: () => void;
  onToggleMute: () => void;
  onToggleCamera: () => void;
  onSendText?: (text: string) => void;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  connectionStatus,
  isCapturing,
  isMuted,
  isCameraActive,
  onStartSession,
  onStopSession,
  onToggleMute,
  onToggleCamera,
}) => {
  const isActive = connectionStatus === "connected" && isCapturing;

  return (
    <div style={styles.container}>
      {/* Control Buttons */}
      <div style={styles.buttonRow}>
        {/* Camera Toggle */}
        {isActive && (
          <button
            onClick={onToggleCamera}
            style={styles.secondaryButton}
            title="Switch camera"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 19H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5" />
              <path d="M13 5h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-5" />
              <path d="m8 12 3-3 3 3" />
              <path d="m16 12-3 3-3-3" />
            </svg>
          </button>
        )}

        {/* Mute Toggle */}
        {isActive && (
          <button
            onClick={onToggleMute}
            style={{
              ...styles.secondaryButton,
              backgroundColor: isMuted
                ? "rgba(239, 68, 68, 0.3)"
                : "rgba(255, 255, 255, 0.08)",
            }}
            title={isMuted ? "Unmute" : "Mute"}
          >
            {isMuted ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="1" y1="1" x2="23" y2="23" />
                <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
                <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2c0 .76-.13 1.49-.36 2.18" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            )}
          </button>
        )}

        {/* Main Action Button */}
        <button
          onClick={isActive ? onStopSession : onStartSession}
          style={{
            ...styles.mainButton,
            backgroundColor: isActive
              ? "rgba(239, 68, 68, 0.9)"
              : "rgba(16, 185, 129, 0.9)",
          }}
          disabled={connectionStatus === "connecting" || connectionStatus === "reconnecting"}
        >
          {connectionStatus === "connecting" || connectionStatus === "reconnecting" ? (
            <div style={styles.spinner} />
          ) : isActive ? (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polygon points="10,8 16,12 10,16" fill="currentColor" />
            </svg>
          )}
        </button>
      </div>

      {/* Status Label */}
      <div style={styles.statusLabel}>
        {getStatusLabel(connectionStatus, isCapturing, isCameraActive)}
      </div>

      <style>{spinnerKeyframes}</style>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getStatusLabel(
  status: ConnectionStatus,
  isCapturing: boolean,
  isCameraActive: boolean
): string {
  switch (status) {
    case "disconnected":
      return "Tap to start Tejas";
    case "connecting":
      return "Connecting to server...";
    case "connected":
      if (isCapturing && isCameraActive) return "Session active";
      return "Connected -- starting media...";
    case "reconnecting":
      return "Reconnecting...";
    case "error":
      return "Connection error";
    default:
      return "";
  }
}

const spinnerKeyframes = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: "fixed",
    bottom: "0",
    left: "0",
    right: "0",
    zIndex: 100,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    padding: "12px 16px 24px",
    background: "linear-gradient(transparent, rgba(10, 10, 26, 0.95))",
    fontFamily: "'Inter', 'SF Pro', -apple-system, sans-serif",
  },
  buttonRow: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  secondaryButton: {
    width: "44px",
    height: "44px",
    borderRadius: "50%",
    border: "1px solid rgba(255, 255, 255, 0.12)",
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    color: "#ccc",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    transition: "background-color 0.2s",
  },
  mainButton: {
    width: "60px",
    height: "60px",
    borderRadius: "50%",
    border: "2px solid rgba(255, 255, 255, 0.2)",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    transition: "background-color 0.2s, transform 0.1s",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
  },
  spinner: {
    width: "20px",
    height: "20px",
    border: "2px solid rgba(255, 255, 255, 0.3)",
    borderTopColor: "#fff",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  statusLabel: {
    marginTop: "8px",
    fontSize: "11px",
    color: "#888",
    fontWeight: 500,
    letterSpacing: "0.3px",
  },
};
