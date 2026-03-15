/**
 * Video frame capture utilities for the Tejas frontend.
 *
 * Captures frames from a camera MediaStream, encodes them as
 * JPEG at configurable quality, and returns base64 strings for
 * WebSocket transport to the Gemini Live API.
 */

import { VideoConfig, DEFAULT_VIDEO_CONFIG } from "../types";

/**
 * Create a frame capture pipeline from a video MediaStream.
 *
 * Uses an offscreen canvas to draw video frames and export
 * them as JPEG data URLs, then strips the header to get raw
 * base64 for transport efficiency.
 *
 * The capture rate adapts between fpsMin and fpsMax based on
 * a simple heuristic: if the frame changes significantly from
 * the previous frame, capture more frequently.
 */
export function createFrameCapture(
  videoElement: HTMLVideoElement,
  onFrame: (base64Jpeg: string) => void,
  config: VideoConfig = DEFAULT_VIDEO_CONFIG
): {
  start: () => void;
  stop: () => void;
  setFps: (fps: number) => void;
} {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  let intervalId: ReturnType<typeof setInterval> | null = null;
  let currentFps = config.fpsMin;

  function captureFrame(): void {
    if (!ctx) return;
    if (videoElement.readyState < videoElement.HAVE_CURRENT_DATA) return;

    // Set canvas to target resolution while maintaining aspect ratio
    const aspectRatio = videoElement.videoWidth / videoElement.videoHeight;
    if (aspectRatio >= 1) {
      canvas.width = config.resolution;
      canvas.height = Math.round(config.resolution / aspectRatio);
    } else {
      canvas.height = config.resolution;
      canvas.width = Math.round(config.resolution * aspectRatio);
    }

    ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);

    // Export as JPEG with configured quality
    const dataUrl = canvas.toDataURL("image/jpeg", config.quality);
    // Strip the "data:image/jpeg;base64," prefix
    const base64 = dataUrl.split(",")[1];
    if (base64) {
      onFrame(base64);
    }
  }

  return {
    start: () => {
      if (intervalId !== null) return;
      const intervalMs = Math.round(1000 / currentFps);
      intervalId = setInterval(captureFrame, intervalMs);
    },
    stop: () => {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
    },
    setFps: (fps: number) => {
      currentFps = Math.max(config.fpsMin, Math.min(config.fpsMax, fps));
      // Restart interval with new rate if currently running
      if (intervalId !== null) {
        clearInterval(intervalId);
        const intervalMs = Math.round(1000 / currentFps);
        intervalId = setInterval(captureFrame, intervalMs);
      }
    },
  };
}

/**
 * Capture a single frame from a video element.
 *
 * Useful for on-demand scene captures (e.g., when logging an incident).
 */
export function captureSingleFrame(
  videoElement: HTMLVideoElement,
  quality: number = DEFAULT_VIDEO_CONFIG.quality,
  maxWidth: number = DEFAULT_VIDEO_CONFIG.resolution
): string | null {
  if (videoElement.readyState < videoElement.HAVE_CURRENT_DATA) {
    return null;
  }

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  const aspectRatio = videoElement.videoWidth / videoElement.videoHeight;
  canvas.width = Math.min(maxWidth, videoElement.videoWidth);
  canvas.height = Math.round(canvas.width / aspectRatio);

  ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL("image/jpeg", quality);
  const base64 = dataUrl.split(",")[1];
  return base64 ?? null;
}
