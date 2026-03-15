/**
 * IncidentHUD component for the Tejas frontend.
 *
 * Heads-Up Display overlay showing real-time incident intelligence:
 * - Victim count and triage summary (color-coded)
 * - Active dispatches with ETAs
 * - Hazard warnings
 * - Recent tool call activity log
 * - Agent transcript feed
 *
 * Positioned on the right side of the viewport, overlaying the
 * camera feed with a semi-transparent dark panel.
 */

import React, { useRef, useEffect } from "react";
import type { IncidentState, ToolCallInfo, Victim } from "../types";

interface IncidentHUDProps {
  incidentState: IncidentState;
}

// ---------------------------------------------------------------------------
// Triage color mapping per START protocol
// ---------------------------------------------------------------------------

const TRIAGE_COLORS: Record<string, string> = {
  immediate: "#ef4444",
  delayed: "#f59e0b",
  minor: "#10b981",
  deceased: "#374151",
  unknown: "#6b7280",
};

const TRIAGE_LABELS: Record<string, string> = {
  immediate: "IMMEDIATE",
  delayed: "DELAYED",
  minor: "MINOR",
  deceased: "DECEASED",
  unknown: "UNKNOWN",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const IncidentHUD: React.FC<IncidentHUDProps> = ({ incidentState }) => {
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll transcript feed
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [incidentState.transcripts]);

  if (!incidentState.isActive) {
    return null;
  }

  const victimsByStatus = groupVictimsByStatus(incidentState.victims);

  return (
    <div style={styles.container}>
      {/* Injected CSS animations */}
      <style>{hudKeyframes}</style>

      {/* AI Vision Scan Indicator — always visible when HUD is active */}
      <div style={styles.scanBanner}>
        <div style={styles.scanDot} />
        <span style={styles.scanLabel}>AI VISION</span>
        <div style={styles.scanLine} />
        <span style={styles.scanStatus}>SCANNING</span>
      </div>

      {/* Triage Summary */}
      <section style={styles.section}>
        <h3 style={styles.sectionTitle}>TRIAGE</h3>
        <div style={styles.triageGrid}>
          {(["immediate", "delayed", "minor", "deceased"] as const).map(
            (status) => (
              <div key={status} style={styles.triageCard}>
                <div
                  style={{
                    ...styles.triageCount,
                    color: TRIAGE_COLORS[status],
                  }}
                >
                  {victimsByStatus[status]?.length ?? 0}
                </div>
                <div
                  style={{
                    ...styles.triageLabel,
                    color: TRIAGE_COLORS[status],
                  }}
                >
                  {TRIAGE_LABELS[status]}
                </div>
              </div>
            )
          )}
        </div>
        {incidentState.victims.length > 0 && (
          <div style={styles.victimList}>
            {incidentState.victims.map((v) => (
              <VictimCard key={v.victimId} victim={v} />
            ))}
          </div>
        )}
      </section>

      {/* Dispatches */}
      {incidentState.dispatches.length > 0 && (
        <section style={styles.section}>
          <h3 style={styles.sectionTitle}>DISPATCHES</h3>
          <div style={styles.dispatchList}>
            {incidentState.dispatches.map((d) => (
              <div key={d.dispatchId} style={styles.dispatchCard}>
                <div style={styles.dispatchType}>
                  {formatResourceType(d.resourceType)}
                </div>
                <div style={styles.dispatchEta}>
                  ETA: {d.etaMinutes} min
                </div>
                <div
                  style={{
                    ...styles.dispatchSeverity,
                    color: severityColor(d.severity),
                  }}
                >
                  {d.severity.toUpperCase()}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Hazards */}
      {incidentState.hazards.length > 0 && (
        <section style={styles.section}>
          <h3 style={{ ...styles.sectionTitle, color: "#ef4444" }}>
            HAZARDS
          </h3>
          {incidentState.hazards.map((h, i) => (
            <div key={i} style={styles.hazardCard}>
              <div style={styles.hazardName}>
                {h.chemicalName}
                {h.unNumber && (
                  <span style={styles.hazardUN}> ({h.unNumber})</span>
                )}
              </div>
              <div style={styles.hazardDistance}>
                Safe distance: {h.safeDistanceFt} ft
              </div>
              {h.hazardClass && (
                <div style={styles.hazardClass}>{h.hazardClass}</div>
              )}
            </div>
          ))}
        </section>
      )}

      {/* Tool Activity */}
      {incidentState.toolCalls.length > 0 && (
        <section style={styles.section}>
          <h3 style={styles.sectionTitle}>ACTIVITY</h3>
          <div style={styles.activityList}>
            {incidentState.toolCalls.slice(-5).map((tc, i) => (
              <ToolCallCard key={i} toolCall={tc} />
            ))}
          </div>
        </section>
      )}

      {/* Imagen Tactical Scene Map */}
      {incidentState.sceneImages && incidentState.sceneImages.length > 0 && (() => {
        const latest = incidentState.sceneImages[incidentState.sceneImages.length - 1];
        return (
          <section style={styles.section}>
            <h3 style={{ ...styles.sectionTitle, color: "#7c3aed" }}>
              {"\u{1F6F0}"} SCENE MAP
            </h3>
            <div style={styles.sceneMapCard}>
              <img
                src={`data:${latest.mimeType};base64,${latest.imageB64}`}
                alt="Imagen tactical scene map"
                style={styles.sceneMapImg}
              />
              <div style={styles.sceneMapMeta}>
                <span style={styles.sceneMapBadge}>Imagen 3</span>
                {latest.victimCount > 0 && (
                  <span style={styles.sceneMapStat}>{latest.victimCount} victims</span>
                )}
                {latest.hazards.length > 0 && (
                  <span style={styles.sceneMapStat}>{latest.hazards.length} hazards</span>
                )}
              </div>
              {latest.sceneDescription && (
                <div style={styles.sceneMapDesc}>{latest.sceneDescription}</div>
              )}
            </div>
          </section>
        );
      })()}

      {/* Transcript */}
      {incidentState.transcripts.length > 0 && (
        <section style={styles.section}>
          <h3 style={styles.sectionTitle}>TRANSCRIPT</h3>
          <div style={styles.transcriptFeed}>
            {incidentState.transcripts.slice(-10).map((t, i) => (
              <div key={i} style={styles.transcriptLine}>
                {t}
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>
        </section>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const VictimCard: React.FC<{ victim: Victim }> = ({ victim }) => (
  <div style={styles.victimCard}>
    <div
      style={{
        ...styles.victimStatus,
        backgroundColor: TRIAGE_COLORS[victim.status] ?? "#666",
      }}
    />
    <div style={styles.victimInfo}>
      <div style={styles.victimId}>{victim.victimId}</div>
      {victim.injuries && (
        <div style={styles.victimInjuries}>{victim.injuries}</div>
      )}
    </div>
  </div>
);

const ToolCallCard: React.FC<{ toolCall: ToolCallInfo }> = ({ toolCall }) => (
  <div style={styles.activityCard}>
    <div
      style={{
        ...styles.activityDot,
        backgroundColor:
          toolCall.status === "completed"
            ? "#10b981"
            : toolCall.status === "executing"
              ? "#f59e0b"
              : "#ef4444",
      }}
    />
    <div style={styles.activityName}>
      {formatToolName(toolCall.name)}
    </div>
    <div style={styles.activityStatus}>
      {toolCall.status === "executing" ? "..." : "done"}
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function groupVictimsByStatus(
  victims: Victim[]
): Record<string, Victim[]> {
  const groups: Record<string, Victim[]> = {};
  for (const v of victims) {
    if (!groups[v.status]) groups[v.status] = [];
    groups[v.status]!.push(v);
  }
  return groups;
}

function formatResourceType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatToolName(name: string): string {
  return name
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function severityColor(severity: string): string {
  switch (severity) {
    case "critical":
      return "#ef4444";
    case "urgent":
      return "#f59e0b";
    case "moderate":
      return "#3b82f6";
    default:
      return "#6b7280";
  }
}

// ---------------------------------------------------------------------------
// Keyframe animations
// ---------------------------------------------------------------------------

const hudKeyframes = `
  @keyframes slideInRight {
    from { opacity: 0; transform: translateX(16px); }
    to   { opacity: 1; transform: translateX(0); }
  }
  @keyframes hazardGlow {
    0%, 100% {
      box-shadow: 0 0 6px rgba(239, 68, 68, 0.25);
      border-color: rgba(239, 68, 68, 0.2);
    }
    50% {
      box-shadow: 0 0 18px rgba(239, 68, 68, 0.7), inset 0 0 8px rgba(239, 68, 68, 0.08);
      border-color: rgba(239, 68, 68, 0.65);
    }
  }
  @keyframes scanPulse {
    0%   { opacity: 0.3; transform: scaleX(0.1); }
    60%  { opacity: 1;   transform: scaleX(1); }
    100% { opacity: 0.3; transform: scaleX(0.1); }
  }
  @keyframes scanDotBlink {
    0%, 100% { opacity: 1;   box-shadow: 0 0 6px #10b981; }
    50%       { opacity: 0.3; box-shadow: none; }
  }
  @keyframes sectionFadeIn {
    from { opacity: 0; transform: translateY(-5px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes triageCountPop {
    0%   { transform: scale(1); }
    50%  { transform: scale(1.15); }
    100% { transform: scale(1); }
  }
`;

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: "fixed",
    top: "60px",
    right: "16px",
    bottom: "100px",
    width: "280px",
    zIndex: 50,
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    overflowY: "auto",
    overflowX: "hidden",
    fontFamily: "'Inter', 'SF Pro', -apple-system, sans-serif",
    scrollbarWidth: "thin",
    scrollbarColor: "rgba(255,255,255,0.1) transparent",
  },
  section: {
    padding: "12px",
    borderRadius: "10px",
    backgroundColor: "rgba(10, 10, 26, 0.85)",
    backdropFilter: "blur(8px)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    animation: "sectionFadeIn 0.35s ease-out",
  },
  sectionTitle: {
    margin: "0 0 8px 0",
    fontSize: "10px",
    fontWeight: 700,
    letterSpacing: "1.5px",
    color: "#888",
    textTransform: "uppercase" as const,
  },

  // Triage
  triageGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr 1fr",
    gap: "6px",
  },
  triageCard: {
    textAlign: "center" as const,
    padding: "6px 4px",
    borderRadius: "6px",
    backgroundColor: "rgba(255, 255, 255, 0.03)",
  },
  triageCount: {
    fontSize: "22px",
    fontWeight: 800,
    fontVariantNumeric: "tabular-nums",
    lineHeight: 1,
  },
  triageLabel: {
    fontSize: "8px",
    fontWeight: 700,
    letterSpacing: "0.5px",
    marginTop: "2px",
  },

  // Victims
  victimList: {
    marginTop: "8px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  victimCard: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "4px 6px",
    borderRadius: "4px",
    backgroundColor: "rgba(255, 255, 255, 0.03)",
  },
  victimStatus: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    flexShrink: 0,
  },
  victimInfo: {
    overflow: "hidden",
  },
  victimId: {
    fontSize: "11px",
    fontWeight: 600,
    color: "#ddd",
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  victimInjuries: {
    fontSize: "10px",
    color: "#888",
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
  },

  // Dispatches
  dispatchList: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  dispatchCard: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "6px 8px",
    borderRadius: "6px",
    backgroundColor: "rgba(255, 255, 255, 0.03)",
  },
  dispatchType: {
    fontSize: "11px",
    fontWeight: 600,
    color: "#ddd",
    flex: 1,
  },
  dispatchEta: {
    fontSize: "11px",
    color: "#10b981",
    fontWeight: 600,
    fontVariantNumeric: "tabular-nums",
  },
  dispatchSeverity: {
    fontSize: "9px",
    fontWeight: 700,
    letterSpacing: "0.5px",
    marginLeft: "8px",
  },

  // Hazards
  hazardCard: {
    padding: "8px",
    borderRadius: "6px",
    backgroundColor: "rgba(239, 68, 68, 0.08)",
    border: "1px solid rgba(239, 68, 68, 0.2)",
    marginBottom: "6px",
    animation: "hazardGlow 2.5s ease-in-out infinite, sectionFadeIn 0.35s ease-out",
  },
  hazardName: {
    fontSize: "12px",
    fontWeight: 700,
    color: "#ef4444",
  },
  hazardUN: {
    fontWeight: 500,
    color: "#ef4444",
    opacity: 0.7,
  },
  hazardDistance: {
    fontSize: "11px",
    color: "#f59e0b",
    fontWeight: 600,
    marginTop: "2px",
  },
  hazardClass: {
    fontSize: "10px",
    color: "#888",
    marginTop: "2px",
  },

  // Activity
  activityList: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  activityCard: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "3px 0",
  },
  activityDot: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    flexShrink: 0,
  },
  activityName: {
    fontSize: "10px",
    color: "#aaa",
    flex: 1,
  },
  activityStatus: {
    fontSize: "10px",
    color: "#666",
    fontWeight: 600,
  },

  // AI Scan Banner
  scanBanner: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "8px 12px",
    borderRadius: "10px",
    backgroundColor: "rgba(5, 20, 15, 0.88)",
    backdropFilter: "blur(8px)",
    border: "1px solid rgba(16, 185, 129, 0.22)",
    boxShadow: "0 0 14px rgba(16, 185, 129, 0.08)",
  },
  scanDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    backgroundColor: "#10b981",
    flexShrink: 0,
    animation: "scanDotBlink 1.5s ease-in-out infinite",
  },
  scanLabel: {
    fontSize: "10px",
    fontWeight: 800,
    letterSpacing: "2px",
    color: "#10b981",
    flexShrink: 0,
  },
  scanLine: {
    flex: 1,
    height: "2px",
    backgroundColor: "#10b981",
    borderRadius: "1px",
    animation: "scanPulse 2.2s ease-in-out infinite",
    transformOrigin: "left center",
  },
  scanStatus: {
    fontSize: "9px",
    fontWeight: 700,
    letterSpacing: "1.5px",
    color: "#10b981",
    opacity: 0.65,
    flexShrink: 0,
  },

  // Transcript
  transcriptFeed: {
    maxHeight: "120px",
    overflowY: "auto",
    scrollbarWidth: "thin",
    scrollbarColor: "rgba(255,255,255,0.1) transparent",
  },
  transcriptLine: {
    fontSize: "11px",
    color: "#bbb",
    lineHeight: 1.5,
    padding: "2px 0",
    borderBottom: "1px solid rgba(255, 255, 255, 0.03)",
  },
  // Imagen tactical scene map
  sceneMapCard: {
    borderRadius: "6px",
    background: "rgba(124, 58, 237, 0.08)",
    border: "1px solid rgba(124, 58, 237, 0.35)",
    overflow: "hidden",
  },
  sceneMapImg: {
    width: "100%",
    display: "block",
    maxHeight: "180px",
    objectFit: "cover" as const,
  },
  sceneMapMeta: {
    display: "flex",
    gap: "6px",
    alignItems: "center",
    padding: "6px 8px 4px",
    flexWrap: "wrap" as const,
  },
  sceneMapBadge: {
    fontSize: "10px",
    fontWeight: 700,
    color: "#fff",
    background: "rgba(124, 58, 237, 0.8)",
    borderRadius: "3px",
    padding: "1px 5px",
    letterSpacing: "0.04em",
  },
  sceneMapStat: {
    fontSize: "10px",
    color: "#d4b8ff",
    lineHeight: 1.4,
  },
  sceneMapDesc: {
    fontSize: "10px",
    color: "#999",
    padding: "0 8px 8px",
    lineHeight: 1.5,
    fontStyle: "italic" as const,
  },
};
