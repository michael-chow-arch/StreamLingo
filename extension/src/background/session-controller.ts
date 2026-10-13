import type { ServerMessage } from "@streamlingo/protocol";
import type { ExtensionSettings } from "../shared/config";
import type { ContentMessage, OffscreenResponse } from "../shared/runtime-messages";
import type { SessionState } from "../shared/session";
import { AppError, errorInfo, errorFromInfo, type UiErrorInfo, type MessageKey } from "../shared/i18n";

export interface SessionHost {
  query(): Promise<SessionState>;
  validateTab(tabId: number): Promise<void>;
  prepare(tabId: number, sessionId: string, settings: ExtensionSettings, signal: AbortSignal): Promise<void>;
  start(tabId: number, sessionId: string, settings: ExtensionSettings, signal: AbortSignal): Promise<OffscreenResponse>;
  stop(sessionId: string): Promise<void>;
  close(): Promise<void>;
  content(tabId: number, message: ContentMessage): Promise<void>;
  changed(state: SessionState): void;
}

interface SessionOperation {
  readonly sessionId: string;
  readonly tabId: number;
  readonly abort: AbortController;
  preparation: Promise<void>;
  cleanup: Promise<void> | null;
}

export class SessionController {
  state: SessionState = { phase: "idle" };
  private queue: Promise<void> = Promise.resolve();
  private active: SessionOperation | null = null;
  private recovery: Promise<void> | null = null;

  constructor(private readonly host: SessionHost) {}

  private set(state: SessionState): void {
    this.state = state;
    this.host.changed(state);
  }

  private serial<T>(operation: () => Promise<T>): Promise<T> {
    const next = this.queue.then(operation, operation);
    this.queue = next.then(() => undefined, () => undefined);
    return next;
  }

  private recover(): Promise<void> {
    this.recovery ??= (async () => {
      try {
        const state = await this.host.query();
        if ("tabId" in state) this.active = this.operation(state.tabId, state.sessionId);
        this.set(state);
      }
      catch {
        await this.host.close();
        this.set({ phase: "error", sessionId: null, message: new AppError("RECOVERY_FAILED").message, errorInfo: { code: "RECOVERY_FAILED" } });
      }
    })();
    return this.recovery;
  }

  async snapshot(): Promise<SessionState> {
    await this.recover();
    return this.state;
  }

  private operation(tabId: number, sessionId: string): SessionOperation {
    return { tabId, sessionId, abort: new AbortController(), preparation: Promise.resolve(), cleanup: null };
  }

  start(tabId: number, settings: ExtensionSettings | (() => Promise<ExtensionSettings>)): Promise<SessionState> {
    return this.serial(async () => {
      await this.recover();
      if (this.active) {
        throw new AppError("SESSION_ACTIVE");
      }
      const sessionId = crypto.randomUUID();
      const operation = this.operation(tabId, sessionId);
      this.active = operation;
      this.set({ phase: "starting", sessionId, tabId });
      const configured = typeof settings === "function" ? settings() : Promise.resolve(settings);
      operation.preparation = (async () => {
        const readySettings = await configured;
        operation.abort.signal.throwIfAborted();
        await this.host.validateTab(tabId);
        operation.abort.signal.throwIfAborted();
        await this.host.prepare(tabId, sessionId, readySettings, operation.abort.signal);
      })();
      // Wrapping the long promise keeps only admission in the control queue.
      return { completion: this.finishStart(operation, configured) };
    }).then(({ completion }) => completion);
  }

  private async finishStart(operation: SessionOperation, settings: Promise<ExtensionSettings>): Promise<SessionState> {
    const { tabId, sessionId, abort } = operation;
    try {
      await operation.preparation;
      abort.signal.throwIfAborted();
      const readySettings = await settings;
      abort.signal.throwIfAborted();
      const response = await this.host.start(tabId, sessionId, readySettings, abort.signal);
      abort.signal.throwIfAborted();
      if (this.active !== operation) throw new AppError("START_CANCELLED");
      if (!response.ok) throw errorFromInfo(response.errorInfo ?? errorInfo(response.error));
      if (response.state.phase === "error") throw errorFromInfo(response.state.errorInfo ?? errorInfo(response.state.message));
      if (response.state.phase !== "starting" && response.state.phase !== "running") throw new AppError("START_FAILED");
      this.set(response.state);
      return this.state;
    } catch (error) {
      if (this.active !== operation || abort.signal.aborted) {
        // Cleanup belongs to the cancelling operation. Never close a new session.
        if (this.state.phase === "error" && this.state.sessionId === sessionId) throw errorFromInfo(this.state.errorInfo ?? errorInfo(this.state.message));
        throw new AppError("START_CANCELLED");
      }
      const info = errorInfo(error);
      const message = error instanceof Error ? error.message : new AppError("START_FAILED").message;
      abort.abort();
      this.set({ phase: "error", sessionId, message, errorInfo: info });
      await this.cleanup(operation);
      throw errorFromInfo(info);
    }
  }

  stop(): Promise<SessionState> {
    return this.serial(async () => {
      await this.recover();
      const operation = this.active;
      if (operation) {
        this.active = null;
        operation.abort.abort();
        this.set({ phase: "stopping", sessionId: operation.sessionId, tabId: operation.tabId });
        await this.cleanup(operation);
      }
      this.set({ phase: "idle" });
      return this.state;
    });
  }

  private cleanup(operation: SessionOperation): Promise<void> {
    operation.cleanup ??= (async () => {
      const clear = () => this.host.content(operation.tabId, { target: "content", type: "CONTENT_STOP", sessionId: operation.sessionId }).catch(() => undefined);
      // Stop capture immediately, independently of a pending preparation call.
      await Promise.all([clear(), this.host.stop(operation.sessionId).catch(() => undefined), operation.preparation.catch(() => undefined)]);
      // A pending createDocument may finish after the first stop. The abort guard
      // prevents it from capturing; closing here finishes that preparation too.
      await clear();
      await this.host.close();
      if (this.active === operation) this.active = null;
    })();
    return operation.cleanup;
  }

  private emit(message: ContentMessage): void {
    if (!this.active) return;
    void this.host.content(this.active.tabId, message).catch(() => undefined);
  }

  async receive(sessionId: string, event: ServerMessage): Promise<void> {
    // Events never join the control queue: OFFSCREEN_START may be awaiting their acknowledgement.
    await this.recover();
    if (!this.active || this.active.sessionId !== sessionId || this.state.phase === "stopping" || this.state.phase === "error") return;
    if (event.session_id !== null && event.session_id !== sessionId) return;
    switch (event.type) {
      case "ready": {
        this.set({ phase: "running", tabId: this.active.tabId, sessionId });
        const key: MessageKey = event.mode === "demo" ? "statusDemo" : event.translation === "disabled" ? "statusDisabled" :
          event.translation === "mock" ? "statusMock" : "statusConnected";
        this.emit({ target: "content", type: "CONTENT_STATUS", sessionId, status: { key } });
        break;
      }
      case "subtitle":
        this.emit({ target: "content", type: "CONTENT_SUBTITLE", subtitle: event });
        break;
      case "error":
        if (event.fatal) this.failed(sessionId, event.message, { code: event.code, detail: event.message });
        // Translation failures/backlog are already attached to their own cue as
        // error/skipped. A late old failure must not become a global banner over
        // unrelated current subtitles or extend their visibility.
        else if (!event.code.startsWith("TRANSLATION_")) {
          this.emit({ target: "content", type: "CONTENT_STATUS", sessionId, status: { error: { code: event.code, detail: event.message } } });
        }
        break;
      case "stopped":
        if (event.reason === "error") this.failed(sessionId, new AppError("SESSION_ENDED").message, { code: "SESSION_ENDED" });
        else void this.stop().catch(() => undefined);
        break;
    }
  }

  async reportFailure(sessionId: string, info: UiErrorInfo): Promise<void> {
    await this.recover();
    this.failed(sessionId, errorFromInfo(info).message, info);
  }

  failed(sessionId: string, message: string, info = errorInfo(message)): void {
    if (!this.active || this.active.sessionId !== sessionId) return;
    const operation = this.active;
    operation.abort.abort();
    this.set({ phase: "error", sessionId, message, errorInfo: info });
    void this.cleanup(operation).catch(() => undefined);
  }

  navigated(tabId: number, sessionId?: string): Promise<void> {
    return this.serial(async () => {
      await this.recover();
      if (!this.active || this.active.tabId !== tabId || (sessionId && this.active.sessionId !== sessionId)) return;
      const operation = this.active;
      this.active = null;
      operation.abort.abort();
      this.set({ phase: "stopping", tabId, sessionId: operation.sessionId });
      await this.cleanup(operation);
      this.set({ phase: "idle" });
    });
  }
}
