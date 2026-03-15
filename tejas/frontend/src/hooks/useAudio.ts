/**
 * React hook for managing audio capture and playback.
 *
 * Provides:
 * - Microphone access and PCM audio capture at 16kHz
 * - Continuous audio playback queue for server responses
 * - Mute/unmute control
 * - Audio level monitoring for UI feedback
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createAudioCapture,
  createAudioPlayer,
  getMicrophoneStream,
} from "../utils/audio";
import type { AudioConfig } from "../types";
import { DEFAULT_AUDIO_CONFIG } from "../types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseAudioReturn {
  /** Whether the microphone is currently capturing. */
  isCapturing: boolean;
  /** Whether the microphone is muted. */
  isMuted: boolean;
  /** Whether audio playback is active. */
  isPlaying: boolean;
  /** Error message if microphone access failed. */
  error: string | null;
  /** Start capturing audio from the microphone. */
  startCapture: (onChunk: (base64Pcm: string) => void) => Promise<void>;
  /** Stop audio capture. */
  stopCapture: () => void;
  /** Toggle mute state. */
  toggleMute: () => void;
  /** Enqueue a base64 PCM audio chunk for playback. */
  playAudio: (base64Pcm: string) => void;
  /** Stop audio playback. */
  stopPlayback: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAudio(
  config: AudioConfig = DEFAULT_AUDIO_CONFIG
): UseAudioReturn {
  const [isCapturing, setIsCapturing] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const captureRef = useRef<ReturnType<typeof createAudioCapture> | null>(null);
  const playerRef = useRef<ReturnType<typeof createAudioPlayer> | null>(null);
  const onChunkRef = useRef<((base64Pcm: string) => void) | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCaptureInternal();
      stopPlaybackInternal();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------------
  // Internal helpers
  // ------------------------------------------------------------------

  function stopCaptureInternal(): void {
    captureRef.current?.stop();
    captureRef.current = null;

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    setIsCapturing(false);
  }

  function stopPlaybackInternal(): void {
    playerRef.current?.stop();
    playerRef.current = null;
    setIsPlaying(false);
  }

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  const startCapture = useCallback(
    async (onChunk: (base64Pcm: string) => void) => {
      setError(null);

      try {
        // Stop any existing capture
        stopCaptureInternal();

        // Request microphone access
        const stream = await getMicrophoneStream(config);
        streamRef.current = stream;

        // Store the callback for mute/unmute handling
        onChunkRef.current = onChunk;

        // Create capture pipeline with a wrapper that respects mute state
        const capture = createAudioCapture(
          streamRef.current,
          (base64Pcm: string) => {
            // Only forward chunks when not muted
            if (!isMuted && onChunkRef.current) {
              onChunkRef.current(base64Pcm);
            }
          },
          () => {
            // VAD detected speech: Interrupt playback immediately
            if (playerRef.current) {
              // We don't destroy the player, just stop current audio
              // But createAudioPlayer.stop() clears the queue and stops sources
              playerRef.current.stop();
            }
          },
          config
        );
        captureRef.current = capture;
        capture.start();

        setIsCapturing(true);

        // Initialize audio player for server responses
        if (!playerRef.current) {
          playerRef.current = createAudioPlayer(config.sampleRate);
          setIsPlaying(true);
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Microphone access denied";

        if (message.includes("NotAllowed") || message.includes("Permission")) {
          setError("Microphone permission denied. Please allow microphone access.");
        } else {
          setError(`Microphone error: ${message}`);
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [config, isMuted]
  );

  const stopCapture = useCallback(() => {
    stopCaptureInternal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const newMuted = !prev;
      // Also mute/unmute the actual media stream tracks
      if (streamRef.current) {
        streamRef.current.getAudioTracks().forEach((track) => {
          track.enabled = !newMuted;
        });
      }
      return newMuted;
    });
  }, []);

  const playAudio = useCallback((base64Pcm: string) => {
    if (!playerRef.current) {
      playerRef.current = createAudioPlayer(config.sampleRate);
      setIsPlaying(true);
    }
    playerRef.current.enqueue(base64Pcm);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.sampleRate]);

  const stopPlayback = useCallback(() => {
    stopPlaybackInternal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    isCapturing,
    isMuted,
    isPlaying,
    error,
    startCapture,
    stopCapture,
    toggleMute,
    playAudio,
    stopPlayback,
  };
}
