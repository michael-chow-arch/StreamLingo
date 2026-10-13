import { AppError, type UiErrorCode, type UiErrorInfo } from "../shared/i18n";
import { parseServerMessage } from "@streamlingo/protocol";
import type { ServerMessage, StartMessage, StopMessage } from "@streamlingo/protocol";
import { translationLanguages, type TranslationMode } from "../shared/config";

export interface LiveClientOptions {
  readonly sessionId: string;
  readonly backendBaseUrl: string;
  readonly translationMode?: TranslationMode;
  readonly onMessage: (message: ServerMessage) => void;
  readonly onFailure: (message: string, errorInfo?: UiErrorInfo) => void;
  readonly socketFactory?: (url: string) => WebSocket;
  readonly handshakeTimeoutMs?: number;
  readonly maxBufferedBytes?: number;
}

export function liveSocketUrl(baseUrl: string): string {
  const url = new URL(baseUrl);
  if ((url.protocol !== "http:" && url.protocol !== "https:") || url.username || url.password) {
    throw new AppError("BACKEND_URL_INVALID");
  }
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/live";
  url.search = "";
  url.hash = "";
  return url.href;
}

/** One socket owns one session. There is no replay or unbounded audio queue. */
export class LiveClient {
  private socket: WebSocket | undefined;
  private ready = false;
  private closed = false;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private resolveStart: (() => void) | undefined;
  private rejectStart: ((reason: Error) => void) | undefined;

  constructor(private readonly options: LiveClientOptions) {}

  start(): Promise<void> {
    if (this.socket || this.closed) return Promise.reject(new AppError("SESSION_ACTIVE"));
    return new Promise<void>((resolve, reject) => {
      this.resolveStart = resolve;
      this.rejectStart = reject;
      try {
        this.socket = (this.options.socketFactory ?? ((url) => new WebSocket(url)))(
          liveSocketUrl(this.options.backendBaseUrl),
        );
      } catch {
        this.fail("SERVICE_UNREACHABLE");
        return;
      }
      const socket = this.socket;
      this.timer = setTimeout(
        () => this.fail("CONNECTION_TIMEOUT"),
        this.options.handshakeTimeoutMs ?? 15_000,
      );
      socket.onopen = () => {
        if (this.closed) return;
        const languages = translationLanguages(this.options.translationMode ?? "en-zh");
        const start: StartMessage = {
          type: "start",
          protocol_version: 1,
          session_id: this.options.sessionId,
          source_language: languages.source,
          target_language: languages.target,
          audio: { encoding: "pcm_s16le", sample_rate: 16_000, channels: 1 },
        };
        try {
          socket.send(JSON.stringify(start));
        } catch {
          this.fail("AUDIO_SEND_FAILED");
        }
      };
      socket.onmessage = (event: MessageEvent<unknown>) => this.receive(event.data);
      socket.onerror = () => this.fail("SERVICE_UNREACHABLE");
      socket.onclose = () => this.fail("CONNECTION_CLOSED");
    });
  }

  sendAudio(packet: ArrayBuffer): void {
    if (this.closed || !this.ready) return;
    const socket = this.socket;
    if (!socket || socket.readyState !== 1) {
      this.fail("CONNECTION_CLOSED");
      return;
    }
    if (packet.byteLength === 0 || packet.byteLength % 2 !== 0 || packet.byteLength > 6_400) {
      this.fail("AUDIO_INVALID");
      return;
    }
    // Two seconds of 16 kHz PCM16 is the maximum unsent audio budget.
    if (socket.bufferedAmount + packet.byteLength > (this.options.maxBufferedBytes ?? 64_000)) {
      this.fail("AUDIO_BACKLOG");
      return;
    }
    try {
      socket.send(packet);
    } catch {
      this.fail("AUDIO_SEND_FAILED");
    }
  }

  close(notifyServer = true): void {
    if (this.closed) return;
    this.closed = true;
    this.ready = false;
    clearTimeout(this.timer);
    this.rejectStart?.(new AppError("START_CANCELLED"));
    this.rejectStart = undefined;
    this.resolveStart = undefined;
    const socket = this.socket;
    if (!socket) return;
    socket.onopen = null;
    socket.onmessage = null;
    socket.onerror = null;
    socket.onclose = null;
    try {
      if (notifyServer && socket.readyState === 1) {
        const stop: StopMessage = { type: "stop", session_id: this.options.sessionId };
        socket.send(JSON.stringify(stop));
      }
    } catch {
      // Closing remains possible if the peer disappeared before stop was sent.
    }
    try {
      socket.close(1000, "session ended");
    } catch {
      // A browser may already be closing a failed handshake.
    }
  }

  private receive(data: unknown): void {
    if (this.closed) return;
    let message: ServerMessage;
    try {
      if (typeof data !== "string" || data.length > 65_536) throw new Error("Invalid frame");
      message = parseServerMessage(JSON.parse(data) as unknown);
    } catch {
      this.fail("INVALID_MESSAGE");
      return;
    }
    if (
      message.session_id !== this.options.sessionId &&
      !(message.type === "error" && message.session_id === null && !this.ready)
    ) {
      this.fail("SESSION_MISMATCH");
      return;
    }
    if (message.type === "ready") {
      if (this.ready) {
        this.fail("INVALID_MESSAGE");
        return;
      }
      const languages = translationLanguages(this.options.translationMode ?? "en-zh");
      if ((message.source_language && message.source_language !== languages.source) ||
          (message.target_language && message.target_language !== languages.target)) {
        this.fail("UNSUPPORTED_LANGUAGE");
        return;
      }
      this.ready = true;
      clearTimeout(this.timer);
      this.resolveStart?.();
      this.resolveStart = undefined;
      this.rejectStart = undefined;
    } else if (!this.ready && message.type !== "error") {
      this.fail("INVALID_MESSAGE");
      return;
    }
    if (message.type === "error" && message.fatal) {
      // The consumer may synchronously close this client while handling an
      // error. Preserve the server's explanation before that cleanup can reject
      // a still-pending handshake with the generic user-stop message.
      this.rejectStart?.(new AppError(message.code, message.message));
      this.rejectStart = undefined;
    }
    this.options.onMessage(message);
    if (message.type === "error" && message.fatal) {
      this.close(false);
    } else if (message.type === "stopped") {
      this.close(false);
    }
  }

  private fail(code: UiErrorCode): void {
    if (this.closed) return;
    const error = new AppError(code);
    this.rejectStart?.(error);
    this.rejectStart = undefined;
    this.close(false);
    this.options.onFailure(error.message, { code });
  }
}
