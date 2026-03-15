/**
 * Audio utility functions for the Tejas frontend.
 *
 * Handles microphone capture as raw PCM 16-bit at 16kHz,
 * base64 encoding for WebSocket transport, and audio
 * playback of PCM responses from the server.
 */

import { AudioConfig, DEFAULT_AUDIO_CONFIG } from "../types";

/**
 * Create an AudioContext configured for 16kHz PCM capture.
 * Reuses a single context to avoid browser limits.
 */
let sharedAudioContext: AudioContext | null = null;

export function getAudioContext(sampleRate?: number): AudioContext {
  if (sharedAudioContext && sharedAudioContext.state !== "closed") {
    return sharedAudioContext;
  }
  sharedAudioContext = new AudioContext({
    sampleRate: sampleRate ?? DEFAULT_AUDIO_CONFIG.sampleRate,
  });
  return sharedAudioContext;
}

/**
 * Request microphone access and return a MediaStream.
 *
 * Configures the stream for speech capture:
 * - Mono channel
 * - Echo cancellation enabled
 * - Noise suppression enabled
 * - Auto gain control enabled
 */
export async function getMicrophoneStream(
  config: AudioConfig = DEFAULT_AUDIO_CONFIG
): Promise<MediaStream> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: config.channels,
      sampleRate: config.sampleRate,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  return stream;
}

/**
 * Create an AudioWorklet-based PCM capture pipeline.
 *
 * Because the Web Audio API does not support direct PCM capture
 * at arbitrary sample rates, we use a ScriptProcessorNode (deprecated
 * but widely supported) as a fallback when AudioWorklet is unavailable.
 *
 * The callback receives base64-encoded PCM 16-bit LE chunks.
 */
export function createAudioCapture(
  stream: MediaStream,
  onChunk: (base64Pcm: string) => void,
  onSpeaking?: () => void,
  config: AudioConfig = DEFAULT_AUDIO_CONFIG
): { start: () => void; stop: () => void } {
  const audioContext = getAudioContext(config.sampleRate);
  const source = audioContext.createMediaStreamSource(stream);

  // Calculate buffer size for the desired chunk duration
  const bufferSize = Math.round(
    (config.sampleRate * config.chunkDurationMs) / 1000
  );
  // ScriptProcessorNode requires power-of-2 buffer sizes
  const roundedBufferSize = nextPowerOf2(bufferSize);

  const processor = audioContext.createScriptProcessor(
    roundedBufferSize,
    config.channels,
    config.channels
  );

  let isCapturing = false;
  let lastSpeakingTime = 0;
  // 0.05 threshold filters out ambient noise (sirens, engines, crowd).
  // 0.02 was too sensitive and caused constant false interruptions outdoors.
  const SPEAKING_THRESHOLD = 0.05;
  // 1-second debounce: prevents rapid-fire interruption from intermittent noise.
  const SPEAKING_DEBOUNCE_MS = 1000;

  processor.onaudioprocess = (event: AudioProcessingEvent) => {
    if (!isCapturing) return;

    const inputData = event.inputBuffer.getChannelData(0);

    // VAD: Calculate RMS (Root Mean Square) to detect speech
    if (onSpeaking) {
      const sumSquares = inputData.reduce((sum, val) => sum + val * val, 0);
      const rms = Math.sqrt(sumSquares / inputData.length);
      const now = Date.now();

      if (rms > SPEAKING_THRESHOLD && (now - lastSpeakingTime > SPEAKING_DEBOUNCE_MS)) {
        lastSpeakingTime = now;
        onSpeaking();
      }
    }

    // Convert Float32 [-1, 1] to Int16 PCM
    const pcm16 = float32ToInt16(inputData);
    const base64 = arrayBufferToBase64(pcm16.buffer as ArrayBuffer);
    onChunk(base64);
  };

  return {
    start: () => {
      if (audioContext.state === "suspended") {
        audioContext.resume().catch(() => {});
      }
      source.connect(processor);
      processor.connect(audioContext.destination);
      isCapturing = true;
    },
    stop: () => {
      isCapturing = false;
      try {
        processor.disconnect();
        source.disconnect();
      } catch {
        // Already disconnected
      }
    },
  };
}

/**
 * Play PCM 16-bit audio received from the server.
 *
 * Decodes the base64 string, converts Int16 PCM back to Float32,
 * creates an AudioBuffer, and plays it through the speakers.
 */
export async function playPcmAudio(
  base64Pcm: string,
  sampleRate: number = DEFAULT_AUDIO_CONFIG.sampleRate
): Promise<void> {
  const audioContext = getAudioContext(sampleRate);

  if (audioContext.state === "suspended") {
    await audioContext.resume();
  }

  const pcmBytes = base64ToArrayBuffer(base64Pcm);
  const int16Array = new Int16Array(pcmBytes);
  const float32Array = int16ToFloat32(int16Array);

  const audioBuffer = audioContext.createBuffer(
    1,
    float32Array.length,
    sampleRate
  );
  audioBuffer.getChannelData(0).set(float32Array);

  const bufferSource = audioContext.createBufferSource();
  bufferSource.buffer = audioBuffer;
  bufferSource.connect(audioContext.destination);
  bufferSource.start();
}

/**
 * Continuously queue and play PCM audio chunks without gaps.
 *
 * Returns a controller object for enqueueing chunks and stopping.
 */
export function createAudioPlayer(
  sampleRate: number = DEFAULT_AUDIO_CONFIG.sampleRate
): {
  enqueue: (base64Pcm: string) => void;
  stop: () => void;
} {
  const audioContext = getAudioContext(sampleRate);
  let nextStartTime = 0;
  const activeSources: AudioBufferSourceNode[] = [];

  return {
    enqueue: (base64Pcm: string) => {
      if (audioContext.state === "suspended") {
        audioContext.resume().catch(() => {});
      }

      const pcmBytes = base64ToArrayBuffer(base64Pcm);
      const int16Array = new Int16Array(pcmBytes);
      const float32Array = int16ToFloat32(int16Array);

      const audioBuffer = audioContext.createBuffer(
        1,
        float32Array.length,
        sampleRate
      );
      audioBuffer.getChannelData(0).set(float32Array);

      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);

      source.onended = () => {
        const index = activeSources.indexOf(source);
        if (index > -1) {
          activeSources.splice(index, 1);
        }
      };

      const currentTime = audioContext.currentTime;
      // If next start time is in the past, reset to now
      if (nextStartTime < currentTime) {
        nextStartTime = currentTime;
      }
      
      const startTime = nextStartTime;
      source.start(startTime);
      nextStartTime += audioBuffer.duration;
      
      activeSources.push(source);
    },
    stop: () => {
      // Stop all currently playing and scheduled sources immediately
      activeSources.forEach((source) => {
        try {
          source.stop();
        } catch (e) {
          // Ignore errors if already stopped
        }
      });
      activeSources.length = 0;
      nextStartTime = 0;
    },
  };
}

// ---------------------------------------------------------------------------
// Conversion Helpers
// ---------------------------------------------------------------------------

/** Convert Float32 audio samples to Int16 PCM. */
export function float32ToInt16(float32: Float32Array): Int16Array {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]!));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16;
}

/** Convert Int16 PCM samples to Float32. */
export function int16ToFloat32(int16: Int16Array): Float32Array {
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i]! / (int16[i]! < 0 ? 0x8000 : 0x7fff);
  }
  return float32;
}

/** Convert an ArrayBuffer to a base64 string. */
export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]!);
  }
  return btoa(binary);
}

/** Convert a base64 string to an ArrayBuffer. */
export function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

/** Return the next power of 2 >= n. */
function nextPowerOf2(n: number): number {
  let p = 1;
  while (p < n) p <<= 1;
  return p;
}
