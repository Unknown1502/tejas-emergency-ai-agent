/**
 * ConnectionStatus component for the Tejas frontend.
 *
 * Displays the current WebSocket connection state as a small
 * indicator badge in the top-left corner of the viewport.
 * Shows session metrics on hover when connected.
 */

import React, { useState, useEffect, useRef } from "react";
import type { ConnectionStatus as ConnectionStatusType, SessionMetrics } from "../types";

interface ConnectionStatusProps {
  status: ConnectionStatusType;
  metrics: SessionMetrics | null;
  lastError: string | null;
}

const STATUS_CONFIG: Record<
  ConnectionStatusType,
  { color: string; label: string; pulse: boolean }
> = {
  disconnected: { color: "#666", label: "Disconnected", pulse: false },
  connecting: { color: "#f59e0b", label: "Connecting", pulse: true },
  connected: { color: "#10b981", label: "Connected", pulse: false },
  reconnecting: { color: "#f59e0b", label: "Reconnecting", pulse: true },
  error: { color: "#ef4444", label: "Error", pulse: false },
};

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  status,
  metrics,
  lastError,
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const [sceneSeconds, setSceneSeconds] = useState(0);
  const timerRef = useRef<number | null>(null);
  const config = STATUS_CONFIG[status];

  // Scene elapsed timer — resets on disconnect
  useEffect(() => {
    if (status === "connected") {
      timerRef.current = window.setInterval(() => {
        setSceneSeconds((s) => s + 1);
      }, 1000);
    } else {
      if (timerRef.current) window.clearInterval(timerRef.current);
      setSceneSeconds(0);
    }
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, [status]);

  return (
    <div
      style={styles.container}
      onMouseEnter={() => setShowDetails(true)}
      onMouseLeave={() => setShowDetails(false)}
    >
      <div style={styles.badge}>
        <div
          style={{
            ...styles.dot,
            backgroundColor: config.color,
            animation: config.pulse ? "pulse 1.5s ease-in-out infinite" : "none",
          }}
        />
        <span style={styles.label}>{config.label}</span>
        {status === "connected" && (
          <>
            <div style={styles.divider} />
            <span style={styles.liveChip as React.CSSProperties}>
              <span style={styles.liveDot} />
              LIVE
            </span>
            <span style={styles.sceneTime}>{formatUptime(sceneSeconds)}</span>
            <div style={styles.divider} />
            <span style={styles.geminiLabel}>GEMINI</span>
          </>
        )}
      </div>

      {showDetails && (metrics || lastError) && (
        <div style={styles.details}>
          {metrics && (
            <>
              <div style={styles.detailRow}>
                <span style={styles.detailLabel}>Uptime</span>
                <span style={styles.detailValue}>
                  {formatUptime(metrics.uptimeSeconds)}
                </span>
              </div>
              <div style={styles.detailRow}>
                <span style={styles.detailLabel}>Audio sent</span>
                <span style={styles.detailValue}>{metrics.audioChunksSent}</span>
              </div>
              <div style={styles.detailRow}>
                <span style={styles.detailLabel}>Video sent</span>
                <span style={styles.detailValue}>{metrics.videoFramesSent}</span>
              </div>
              <div style={styles.detailRow}>
                <span style={styles.detailLabel}>Tool calls</span>
                <span style={styles.detailValue}>{metrics.toolCallsExecuted}</span>
              </div>
            </>
          )}
          {lastError && (
            <div style={styles.errorRow}>
              {lastError}
            </div>
          )}
        </div>
      )}

      <style>{pulseKeyframes}</style>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUptime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

const pulseKeyframes = `
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  @keyframes liveGlow {
    0%, 100% { box-shadow: 0 0 4px rgba(239, 68, 68, 0.5); }
    50% { box-shadow: 0 0 12px rgba(239, 68, 68, 0.9), 0 0 20px rgba(239, 68, 68, 0.3); }
  }
  @keyframes liveDotPulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(0.7); }
  }
`;

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: "fixed",
    bottom: "96px",
    left: "16px",
    zIndex: 100,
    fontFamily: "'Inter', 'SF Pro', -apple-system, sans-serif",
  },
  badge: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 12px",
    borderRadius: "20px",
    backgroundColor: "rgba(10, 10, 26, 0.8)",
    backdropFilter: "blur(8px)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    cursor: "default",
  },
  dot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    flexShrink: 0,
  },
  label: {
    fontSize: "12px",
    fontWeight: 600,
    color: "#ccc",
    letterSpacing: "0.3px",
  },
  details: {
    marginTop: "8px",
    padding: "10px 12px",
    borderRadius: "8px",
    backgroundColor: "rgba(10, 10, 26, 0.9)",
    backdropFilter: "blur(8px)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    minWidth: "180px",
  },
  detailRow: {
    display: "flex",
    justifyContent: "space-between",
    padding: "3px 0",
  },
  detailLabel: {
    fontSize: "11px",
    color: "#888",
  },
  detailValue: {
    fontSize: "11px",
    color: "#ddd",
    fontWeight: 600,
    fontVariantNumeric: "tabular-nums",
  },
  errorRow: {
    marginTop: "6px",
    paddingTop: "6px",
    borderTop: "1px solid rgba(239, 68, 68, 0.3)",
    fontSize: "11px",
    color: "#ef4444",
    lineHeight: 1.4,
  },
  divider: {
    width: "1px",
    height: "12px",
    backgroundColor: "rgba(255,255,255,0.15)",
    flexShrink: 0,
  },
  liveChip: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    padding: "2px 7px",
    borderRadius: "10px",
    backgroundColor: "rgba(239, 68, 68, 0.12)",
    border: "1px solid rgba(239, 68, 68, 0.45)",
    animation: "liveGlow 2s ease-in-out infinite",
    fontSize: "9px",
    fontWeight: 800,
    letterSpacing: "1.5px",
    color: "#ef4444",
  },
  liveDot: {
    width: "5px",
    height: "5px",
    borderRadius: "50%",
    backgroundColor: "#ef4444",
    display: "inline-block",
    animation: "liveDotPulse 1s ease-in-out infinite",
    flexShrink: 0,
  },
  sceneTime: {
    fontSize: "12px",
    fontWeight: 700,
    color: "#10b981",
    fontVariantNumeric: "tabular-nums",
    letterSpacing: "0.5px",
  },
  geminiLabel: {
    fontSize: "9px",
    fontWeight: 800,
    letterSpacing: "2px",
    color: "#4285f4",
    padding: "2px 6px",
    borderRadius: "4px",
    backgroundColor: "rgba(66, 133, 244, 0.1)",
    border: "1px solid rgba(66, 133, 244, 0.3)",
  },
};
