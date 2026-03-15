/**
 * CameraView component for the Tejas frontend.
 *
 * Renders the live camera feed as a full-viewport background with
 * a semi-transparent overlay. The video element acts as the source
 * for the frame capture pipeline managed by the useCamera hook.
 */

import React from "react";

interface CameraViewProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  isActive: boolean;
  facingMode: "user" | "environment";
}

export const CameraView: React.FC<CameraViewProps> = ({
  videoRef,
  isActive,
  facingMode,
}) => {
  return (
    <div style={styles.container}>
      <video
        ref={videoRef as React.Ref<HTMLVideoElement>}
        autoPlay
        playsInline
        muted
        style={{
          ...styles.video,
          transform: facingMode === "user" ? "scaleX(-1)" : "none",
          opacity: isActive ? 1 : 0.3,
        }}
      />
      {!isActive && (
        <div style={styles.placeholder}>
          <div style={styles.placeholderIcon}>
            <svg
              width="64"
              height="64"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </div>
          <p style={styles.placeholderText}>Camera inactive</p>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100vw",
    height: "100vh",
    overflow: "hidden",
    backgroundColor: "#0a0a1a",
    zIndex: 0,
  },
  video: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  },
  placeholder: {
    position: "absolute",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "12px",
    color: "#555",
  },
  placeholderIcon: {
    opacity: 0.5,
  },
  placeholderText: {
    fontSize: "14px",
    fontWeight: 500,
    letterSpacing: "0.5px",
    textTransform: "uppercase" as const,
  },
};
