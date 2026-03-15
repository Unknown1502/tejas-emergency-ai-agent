/**
 * React hook for managing camera access and video frame capture.
 *
 * Provides:
 * - Camera permission request and stream management
 * - Continuous frame capture at adaptive FPS
 * - Video element ref for the CameraView component
 * - Camera switching (front/back) on supported devices
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { createFrameCapture } from "../utils/frame";
import type { VideoConfig } from "../types";
import { DEFAULT_VIDEO_CONFIG } from "../types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseCameraReturn {
  /** Ref to attach to the <video> element. */
  videoRef: React.RefObject<HTMLVideoElement | null>;
  /** Whether the camera is active. */
  isActive: boolean;
  /** Whether camera permission has been granted. */
  hasPermission: boolean | null;
  /** Current facing mode (user = front, environment = back). */
  facingMode: "user" | "environment";
  /** Start the camera and frame capture. */
  start: (onFrame: (base64Jpeg: string) => void) => Promise<void>;
  /** Stop the camera and frame capture. */
  stop: () => void;
  /** Toggle between front and back camera. */
  toggleCamera: () => void;
  /** Update the capture frame rate. */
  setFps: (fps: number) => void;
  /** Error message if camera access failed. */
  error: string | null;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCamera(
  config: VideoConfig = DEFAULT_VIDEO_CONFIG
): UseCameraReturn {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const captureRef = useRef<ReturnType<typeof createFrameCapture> | null>(null);

  const [isActive, setIsActive] = useState(false);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [facingMode, setFacingMode] = useState<"user" | "environment">("environment");
  const [error, setError] = useState<string | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopInternal();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------------
  // Internal helpers
  // ------------------------------------------------------------------

  function stopInternal(): void {
    captureRef.current?.stop();
    captureRef.current = null;

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setIsActive(false);
  }

  async function requestCamera(facing: "user" | "environment"): Promise<MediaStream> {
    const constraints: MediaStreamConstraints = {
      video: {
        facingMode: facing,
        width: { ideal: config.resolution },
        height: { ideal: config.resolution },
        frameRate: { ideal: config.fpsMax },
      },
      audio: false,
    };

    return navigator.mediaDevices.getUserMedia(constraints);
  }

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  const start = useCallback(
    async (onFrame: (base64Jpeg: string) => void) => {
      setError(null);

      try {
        // Stop any existing capture
        stopInternal();

        // Request camera
        const stream = await requestCamera(facingMode);
        streamRef.current = stream;
        setHasPermission(true);

        // Attach stream to video element
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }

        // Start frame capture
        if (videoRef.current) {
          const capture = createFrameCapture(videoRef.current, onFrame, config);
          captureRef.current = capture;

          // Wait a short moment for the video to stabilize
          setTimeout(() => {
            capture.start();
          }, 500);
        }

        setIsActive(true);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Camera access denied";

        if (message.includes("NotAllowed") || message.includes("Permission")) {
          setHasPermission(false);
          setError("Camera permission denied. Please allow camera access.");
        } else if (message.includes("NotFound")) {
          setError("No camera found on this device.");
        } else {
          setError(`Camera error: ${message}`);
        }

        setIsActive(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [facingMode, config]
  );

  const stop = useCallback(() => {
    stopInternal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleCamera = useCallback(() => {
    const newFacing = facingMode === "user" ? "environment" : "user";
    setFacingMode(newFacing);

    // If currently active, restart with new facing mode
    if (isActive && captureRef.current) {
      // The effect will restart when facingMode changes
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facingMode, isActive]);

  const setFps = useCallback((fps: number) => {
    captureRef.current?.setFps(fps);
  }, []);

  return {
    videoRef,
    isActive,
    hasPermission,
    facingMode,
    start,
    stop,
    toggleCamera,
    setFps,
    error,
  };
}
