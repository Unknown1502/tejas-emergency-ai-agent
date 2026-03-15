/**
 * WebSocket service for the Tejas frontend.
 *
 * Manages the WebSocket connection lifecycle, message serialization,
 * and automatic reconnection. Provides a typed event-based API for
 * sending and receiving messages.
 */

import type {
  ClientMessage,
  ServerMessage,
  ConnectionStatus,
} from "../types";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

export interface WebSocketConfig {
  /** WebSocket endpoint URL. Defaults to ws://localhost:8080/ws/stream */
  url: string;
  /** Maximum reconnection attempts before giving up. */
  maxReconnectAttempts: number;
  /** Base delay between reconnections (ms). Doubles with each attempt. */
  reconnectBaseDelay: number;
  /** Maximum reconnection delay (ms). */
  reconnectMaxDelay: number;
}

const DEFAULT_CONFIG: WebSocketConfig = {
  // VITE_WS_URL: set at build time for Cloud Run deployments where the
  // frontend and backend are on different domains. Pass it via:
  //   VITE_WS_URL=wss://tejas-backend-HASH-uc.a.run.app/ws/stream npm run build
  // If not set, auto-derives from window.location.host so the nginx proxy
  // transparently forwards /ws/ to the backend on the same domain.
  url: (import.meta.env.VITE_WS_URL as string | undefined) ??
    `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/stream`,
  maxReconnectAttempts: 5,
  reconnectBaseDelay: 1000,
  reconnectMaxDelay: 30000,
};

// ---------------------------------------------------------------------------
// Event Types
// ---------------------------------------------------------------------------

export type WebSocketEventType =
  | "message"
  | "status"
  | "error"
  | "open"
  | "close";

export type WebSocketEventHandler<T = unknown> = (data: T) => void;

// ---------------------------------------------------------------------------
// WebSocket Service
// ---------------------------------------------------------------------------

export class WebSocketService {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;
  private _status: ConnectionStatus = "disconnected";

  // Event listeners
  private messageHandlers: WebSocketEventHandler<ServerMessage>[] = [];
  private statusHandlers: WebSocketEventHandler<ConnectionStatus>[] = [];
  private errorHandlers: WebSocketEventHandler<string>[] = [];

  constructor(config: Partial<WebSocketConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  // ------------------------------------------------------------------
  // Connection Management
  // ------------------------------------------------------------------

  /**
   * Open a WebSocket connection to the backend.
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.intentionalClose = false;
    this.setStatus("connecting");

    try {
      this.ws = new WebSocket(this.config.url);
      this.ws.binaryType = "arraybuffer";

      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Connection failed";
      this.emitError(message);
      this.setStatus("error");
      this.scheduleReconnect();
    }
  }

  /**
   * Close the WebSocket connection intentionally.
   */
  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimeout();

    if (this.ws) {
      this.ws.close(1000, "Client disconnect");
      this.ws = null;
    }

    this.setStatus("disconnected");
  }

  /**
   * Send a typed message to the server.
   */
  send(message: ClientMessage): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }

    try {
      this.ws.send(JSON.stringify(message));
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Send a raw audio chunk (base64 PCM).
   */
  sendAudio(base64Pcm: string): boolean {
    return this.send({ type: "audio", data: base64Pcm });
  }

  /**
   * Send a raw video frame (base64 JPEG).
   */
  sendVideo(base64Jpeg: string): boolean {
    return this.send({ type: "video", data: base64Jpeg });
  }

  /**
   * Send session initialization data.
   */
  sendSessionInit(data: {
    incidentId?: string;
    gpsLat?: number;
    gpsLng?: number;
  }): boolean {
    return this.send({
      type: "session_init",
      data: {
        incident_id: data.incidentId,
        gps_lat: data.gpsLat,
        gps_lng: data.gpsLng,
      },
    });
  }

  /**
   * Send a text message (fallback for non-audio input).
   */
  sendText(text: string): boolean {
    return this.send({ type: "text", data: text });
  }

  /**
   * Signal the end of the user's speaking turn.
   */
  sendEndTurn(): boolean {
    return this.send({ type: "end_turn" });
  }

  // ------------------------------------------------------------------
  // Event Subscription
  // ------------------------------------------------------------------

  onMessage(handler: WebSocketEventHandler<ServerMessage>): () => void {
    this.messageHandlers.push(handler);
    return () => {
      this.messageHandlers = this.messageHandlers.filter((h) => h !== handler);
    };
  }

  onStatus(handler: WebSocketEventHandler<ConnectionStatus>): () => void {
    this.statusHandlers.push(handler);
    return () => {
      this.statusHandlers = this.statusHandlers.filter((h) => h !== handler);
    };
  }

  onError(handler: WebSocketEventHandler<string>): () => void {
    this.errorHandlers.push(handler);
    return () => {
      this.errorHandlers = this.errorHandlers.filter((h) => h !== handler);
    };
  }

  // ------------------------------------------------------------------
  // Getters
  // ------------------------------------------------------------------

  get status(): ConnectionStatus {
    return this._status;
  }

  get isConnected(): boolean {
    return this._status === "connected";
  }

  // ------------------------------------------------------------------
  // Internal Handlers
  // ------------------------------------------------------------------

  private handleOpen(): void {
    this.reconnectAttempts = 0;
    this.setStatus("connected");
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: ServerMessage =
        typeof event.data === "string"
          ? JSON.parse(event.data)
          : JSON.parse(new TextDecoder().decode(event.data));

      for (const handler of this.messageHandlers) {
        handler(message);
      }
    } catch {
      // Ignore malformed messages
    }
  }

  private handleError(): void {
    this.emitError("WebSocket connection error");
    this.setStatus("error");
  }

  private handleClose(event: CloseEvent): void {
    if (this.intentionalClose) {
      this.setStatus("disconnected");
      return;
    }

    // Unexpected close -- attempt reconnection
    this.setStatus("reconnecting");
    this.scheduleReconnect();

    if (event.code !== 1000) {
      this.emitError(`Connection closed: code=${event.code}, reason=${event.reason}`);
    }
  }

  // ------------------------------------------------------------------
  // Reconnection
  // ------------------------------------------------------------------

  private scheduleReconnect(): void {
    if (this.intentionalClose) return;
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      this.setStatus("error");
      this.emitError("Maximum reconnection attempts reached.");
      return;
    }

    const delay = Math.min(
      this.config.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts),
      this.config.reconnectMaxDelay
    );

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private clearReconnectTimeout(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  private setStatus(status: ConnectionStatus): void {
    if (this._status === status) return;
    this._status = status;
    for (const handler of this.statusHandlers) {
      handler(status);
    }
  }

  private emitError(message: string): void {
    for (const handler of this.errorHandlers) {
      handler(message);
    }
  }
}

// ---------------------------------------------------------------------------
// Singleton factory
// ---------------------------------------------------------------------------

let _instance: WebSocketService | null = null;

export function getWebSocketService(
  config?: Partial<WebSocketConfig>
): WebSocketService {
  if (!_instance) {
    _instance = new WebSocketService(config);
  }
  return _instance;
}
