/**
 * SceneHeader — top command bar for Tejas.
 *
 * Always-visible 48px header strip anchored to the top viewport edge.
 * Shows: brand identity | active incident ID | GPS fix | Gemini Live badge.
 *
 * Designed to pass the "EOC aesthetic" glance test — looks like
 * a real emergency-operations-center dispatch console, not a demo app.
 */

import React from "react";

interface SceneHeaderProps {
  incidentId: string | null;
  gpsLat: number | null;
  gpsLng: number | null;
  isActive: boolean;
}

export const SceneHeader: React.FC<SceneHeaderProps> = ({
  incidentId,
  gpsLat,
  gpsLng,
  isActive,
}) => {
  return (
    <div style={styles.container}>
      <style>{headerKeyframes}</style>

      {/* ── Left: Brand ─────────────────────────────────────────────── */}
      <div style={styles.brand}>
        <div style={isActive ? (styles.brandDotActive as React.CSSProperties) : styles.brandDot} />
        <span style={styles.brandName}>TEJAS</span>
        <span style={styles.brandSub}>INCIDENT&nbsp;AI</span>
      </div>

      {/* ── Center: Incident ID / standby ───────────────────────────── */}
      <div style={styles.center}>
        {isActive && incidentId ? (
          <span style={styles.incidentId}>{incidentId}</span>
        ) : (
          <span style={styles.standby}>STANDBY</span>
        )}
      </div>

      {/* ── Right: GPS + Gemini badge ────────────────────────────────── */}
      <div style={styles.right}>
        {gpsLat !== null && gpsLng !== null ? (
          <span style={styles.gps}>
            {Math.abs(gpsLat).toFixed(4)}°{gpsLat >= 0 ? "N" : "S"}{" "}
            {Math.abs(gpsLng).toFixed(4)}°{gpsLng >= 0 ? "E" : "W"}
          </span>
        ) : (
          <span style={styles.gpsPending}>GPS&nbsp;···</span>
        )}
        {isActive && <span style={styles.aiBadge}>GEMINI&nbsp;LIVE</span>}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Keyframes
// ---------------------------------------------------------------------------

const headerKeyframes = `
  @keyframes headerDotActive {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5); }
    60%       { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
  }
  @keyframes incidentIdGlow {
    0%, 100% { box-shadow: 0 0 0 rgba(245,158,11,0); }
    50%       { box-shadow: 0 0 8px rgba(245,158,11,0.35); }
  }
`;

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    height: "48px",
    zIndex: 110,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 16px",
    backgroundColor: "rgba(8, 8, 20, 0.94)",
    backdropFilter: "blur(14px)",
    WebkitBackdropFilter: "blur(14px)",
    borderBottom: "1px solid rgba(255, 255, 255, 0.07)",
    fontFamily: "'Inter', 'SF Pro', -apple-system, sans-serif",
  },

  // Brand block
  brand: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flex: "0 0 auto",
  },
  brandDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    backgroundColor: "#333",
    flexShrink: 0,
  },
  brandDotActive: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    backgroundColor: "#ef4444",
    flexShrink: 0,
    animation: "headerDotActive 1.8s ease-in-out infinite",
  },
  brandName: {
    fontSize: "16px",
    fontWeight: 900,
    letterSpacing: "5px",
    color: "#ffffff",
    lineHeight: 1,
  },
  brandSub: {
    fontSize: "8px",
    fontWeight: 700,
    letterSpacing: "2px",
    color: "#444",
    alignSelf: "flex-end",
    marginBottom: "2px",
  },

  // Center
  center: {
    flex: 1,
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },
  incidentId: {
    fontSize: "11px",
    fontWeight: 700,
    letterSpacing: "2.5px",
    color: "#f59e0b",
    fontVariantNumeric: "tabular-nums",
    padding: "4px 12px",
    borderRadius: "6px",
    backgroundColor: "rgba(245, 158, 11, 0.1)",
    border: "1px solid rgba(245, 158, 11, 0.28)",
    animation: "incidentIdGlow 3s ease-in-out infinite",
  },
  standby: {
    fontSize: "10px",
    fontWeight: 700,
    letterSpacing: "4px",
    color: "#2a2a3a",
  },

  // Right
  right: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flex: "0 0 auto",
  },
  gps: {
    fontSize: "10px",
    fontWeight: 600,
    color: "#4b9eff",
    fontVariantNumeric: "tabular-nums",
    letterSpacing: "0.3px",
  },
  gpsPending: {
    fontSize: "10px",
    color: "#2a2a3a",
    letterSpacing: "1px",
  },
  aiBadge: {
    fontSize: "9px",
    fontWeight: 800,
    letterSpacing: "1.5px",
    color: "#4285f4",
    padding: "3px 8px",
    borderRadius: "5px",
    backgroundColor: "rgba(66, 133, 244, 0.1)",
    border: "1px solid rgba(66, 133, 244, 0.28)",
  },
};
