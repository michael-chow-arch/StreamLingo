import type { ContentMessage } from "../shared/runtime-messages";
import { SubtitleStore } from "./subtitle-store";
import { SubtitleView } from "./subtitle-view";
import { DEFAULT_UI_LANGUAGE, type UiLanguage } from "../shared/i18n";
import { observeUiLanguage } from "../shared/language-preference";
import { translationLanguages, DEFAULT_SETTINGS } from "../shared/config";

function install(): void {
  const global = globalThis as typeof globalThis & { __streamlingoContentInstalled?: boolean };
  if (global.__streamlingoContentInstalled) return;
  global.__streamlingoContentInstalled = true;
  let store: SubtitleStore | undefined;
  let view: SubtitleView | undefined;
  let observer: MutationObserver | undefined;
  let videoKey = "";
  let renderedWindow: string | undefined;
  let expiryTimer: ReturnType<typeof setTimeout> | undefined;
  let language: UiLanguage = DEFAULT_UI_LANGUAGE;
  let languages = translationLanguages(DEFAULT_SETTINGS.translationMode);
  const stopLanguageObserver = observeUiLanguage((value) => {
    language = value;
    view?.setLanguage(value);
  });

  function currentVideo(): string {
    const url = new URL(location.href);
    return `${url.pathname}:${url.searchParams.get("v") ?? ""}`;
  }

  function clear(): void {
    observer?.disconnect();
    observer = undefined;
    view?.dispose();
    view = undefined;
    store = undefined;
    renderedWindow = undefined;
    clearTimeout(expiryTimer);
    expiryTimer = undefined;
  }

  function renderSubtitles(): void {
    if (!store || !view) return;
    clearTimeout(expiryTimer);
    const now = performance.now();
    const window = store.readingWindow(now);
    const key = window.items.map(({ cue, kind, pageIndex }) => `${kind}:${cue.segment_id}:${cue.revision}:${pageIndex ?? ""}`).join("|") + `:${window.pendingCount}`;
    if (key !== renderedWindow) {
      renderedWindow = key;
      view.render(window);
    }
    expiryTimer = window.nextChangeAt === null ? undefined : setTimeout(renderSubtitles, Math.max(1, window.nextChangeAt - now));
  }

  function navigate(): void {
    if (!store) return;
    const sessionId = store.sessionId;
    clear();
    void chrome.runtime.sendMessage({ target: "background", type: "CONTENT_NAVIGATED", sessionId }).catch(() => {});
  }

  function mount(): void {
    if (!view) return;
    if (currentVideo() !== videoKey) { navigate(); return; }
    const player = document.querySelector<HTMLElement>("#movie_player, .html5-video-player");
    if (player && view.host.parentElement !== player) player.append(view.host);
  }

  chrome.runtime.onMessage.addListener((message: ContentMessage, sender, respond) => {
    if (sender.id !== chrome.runtime.id || message?.target !== "content") return false;
    if (message.type === "CONTENT_START") {
      clear();
      store = new SubtitleStore(message.sessionId);
      languages = translationLanguages(message.settings.translationMode);
      store.setReadingVisible(!document.hidden, performance.now());
      view = new SubtitleView(message.settings, language);
      videoKey = currentVideo();
      observer = new MutationObserver(mount);
      observer.observe(document.documentElement, { subtree: true, childList: true });
      mount();
    } else if (message.type === "CONTENT_STOP" && message.sessionId === store?.sessionId) {
      clear();
    } else if (message.type === "CONTENT_STATUS" && message.sessionId === store?.sessionId) {
      view?.setStatus(message.status);
    } else if (message.type === "CONTENT_SUBTITLE" && store?.upsert({ ...message.subtitle,
      source_language: message.subtitle.source_language ?? languages.source,
      target_language: message.subtitle.target_language ?? languages.target })) {
      renderSubtitles();
    }
    respond({ ok: true });
    return false;
  });
  document.addEventListener("yt-navigate-start", navigate);
  document.addEventListener("visibilitychange", () => {
    if (!store) return;
    store.setReadingVisible(!document.hidden, performance.now());
    renderSubtitles();
  });
  document.addEventListener("fullscreenchange", mount);
  window.addEventListener("pagehide", () => { navigate(); stopLanguageObserver(); });
}

install();
