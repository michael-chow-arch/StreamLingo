import type { SubtitleMessage, TargetLanguage } from "@streamlingo/protocol";
import { pageCapacity, pageCharacterCount, paginateTranslation, visibleCharacterCount } from "./subtitle-pagination";

export const SUBTITLE_VISIBLE_MS = 12_000;
export const MIN_READING_MS = 4_000;
export const MAX_READING_MS = 8_000;

/** A product default, not a claim about every viewer's reading speed. */
export function readingDurationMs(text: string, language: TargetLanguage = "zh-CN"): number {
  const words = language === "en"
    ? [...new Intl.Segmenter("en", { granularity: "word" }).segment(text)].filter(part => part.isWordLike).length : 0;
  const duration = language === "en" ? Math.max(words * 1_000 / 3, visibleCharacterCount(text) * 50)
    : visibleCharacterCount(text) * 1_000 / 8;
  return Math.min(MAX_READING_MS, Math.max(MIN_READING_MS, Math.ceil(duration)));
}

export interface ReadingItem {
  readonly cue: SubtitleMessage;
  readonly kind: "translated" | "current";
  readonly expiresAt: number;
  readonly translatedText?: string;
  readonly pageIndex?: number;
  readonly pageCount?: number;
}

export interface ReadingWindow {
  readonly items: readonly ReadingItem[];
  readonly nextChangeAt: number | null;
  /** Completed translation pages that have not appeared yet. */
  readonly pendingCount: number;
  readonly historyVersion: number;
  readonly completedCount: number;
}

interface TranslationPage {
  readonly cue: SubtitleMessage;
  readonly translatedText: string;
  readonly pageIndex: number;
  readonly pageCount: number;
}

interface ActiveGroup {
  readonly pages: readonly TranslationPage[];
  readonly expiresAt: number;
  readonly protectedUntil: number;
}

/** A session-scoped, lossless automatic reader. Destroy it when the session ends. */
export class SubtitleStore {
  private readonly items = new Map<number, SubtitleMessage>();
  private readonly changedAt = new Map<number, number>();
  private readonly completed = new Map<number, SubtitleMessage>();
  // Pages retain immutable snapshots. A later revision must not rewrite a page
  // already being read; corrected translations enter the queue in their turn.
  private readonly pages: TranslationPage[] = [];
  private nextPageIndex = 0;
  private active: ActiveGroup | undefined;
  private hiddenAt: number | null = null;
  private highWaterMark = 0;
  private historyVersion = 0;

  // Accept the former limit argument for callers upgrading from the bounded
  // cache. It is intentionally ignored: this session never evicts a cue.
  constructor(readonly sessionId: string, _legacyLimit?: number) {}

  upsert(message: SubtitleMessage, now = performance.now()): boolean {
    if (message.session_id !== this.sessionId) return false;
    const previous = this.items.get(message.segment_id);
    if (previous) {
      if (message.revision <= previous.revision) return false;
      if (previous.source_final && (!message.source_final ||
          message.source_text !== previous.source_text ||
          message.start_ms !== previous.start_ms || message.end_ms !== previous.end_ms)) return false;
    }
    const previousCompletion = this.completed.get(message.segment_id);
    const newTranslation = message.translation.status === "complete" &&
      (previousCompletion?.translation.status !== "complete" ||
        previousCompletion.translation.text !== message.translation.text ||
        previousCompletion.translation.is_mock !== message.translation.is_mock ||
        previousCompletion.target_language !== message.target_language);
    const changed = !previous || previous.source_text !== message.source_text ||
      previous.source_final !== message.source_final || previous.translation.status !== message.translation.status || newTranslation;
    if (changed) this.changedAt.set(message.segment_id, now);

    this.items.set(message.segment_id, message);
    this.highWaterMark = Math.max(this.highWaterMark, message.segment_id);
    this.historyVersion++;
    if (message.translation.status === "complete") {
      this.completed.set(message.segment_id, message);
      if (newTranslation) {
        const language = message.target_language ?? "zh-CN";
        const textPages = paginateTranslation(message.translation.text, pageCapacity(language), language);
        textPages.forEach((translatedText, pageIndex) => this.pages.push({
          cue: message, translatedText, pageIndex, pageCount: textPages.length,
        }));
      }
    }
    return true;
  }

  latest(): SubtitleMessage | undefined {
    return this.items.get(this.highWaterMark);
  }

  values(): readonly SubtitleMessage[] {
    return [...this.items.values()].sort((a, b) => a.segment_id - b.segment_id);
  }

  completedValues(): readonly SubtitleMessage[] {
    return [...this.completed.values()].sort((a, b) => a.segment_id - b.segment_id);
  }

  /** Browser visibility only; receiving subtitles continues while reading rests. */
  setReadingVisible(visible: boolean, now = performance.now()): void {
    if (!visible) {
      if (this.hiddenAt === null) this.hiddenAt = now;
      return;
    }
    if (this.hiddenAt === null) return;
    const hiddenDuration = Math.max(0, now - this.hiddenAt);
    if (this.active) {
      this.active = { ...this.active,
        protectedUntil: this.active.protectedUntil + hiddenDuration,
        expiresAt: this.active.expiresAt + hiddenDuration };
    }
    for (const [id, changedAt] of this.changedAt) {
      // Existing previews keep their remaining time. Text first changed while
      // hidden receives its full preview budget when the viewer comes back.
      this.changedAt.set(id, changedAt <= this.hiddenAt ? changedAt + hiddenDuration : now);
    }
    this.hiddenAt = null;
  }

  readingWindow(now = performance.now()): ReadingWindow {
    const visible = this.hiddenAt === null;
    const readingTime = this.hiddenAt ?? now;
    if (visible && this.nextPageIndex < this.pages.length && (!this.active || this.active.protectedUntil <= now)) {
      const first = this.pages[this.nextPageIndex++]!;
      const group = [first];
      const second = this.pages[this.nextPageIndex];
      const language = first.cue.target_language ?? "zh-CN";
      // Pair only adjacent short, complete cues. Long translations remain
      // contiguous single-page turns, and each row retains its own source cue.
      if (second && first.pageCount === 1 && second.pageCount === 1 &&
          first.cue.segment_id !== second.cue.segment_id &&
          language === (second.cue.target_language ?? "zh-CN") &&
          pageCharacterCount(first.translatedText + " " + second.translatedText, language) <= pageCapacity(language)) {
        group.push(second);
        this.nextPageIndex++;
      }
      // Form exactly one fixed group. Never add a late arrival mid-read or let
      // timer throttling consume reading time before a group has appeared.
      this.active = { pages: group, expiresAt: now + SUBTITLE_VISIBLE_MS,
        protectedUntil: now + readingDurationMs(group.map(page => page.translatedText).join(" "), language) };
    } else if (visible && this.active && this.active.expiresAt <= now) {
      this.active = undefined;
    }

    const pendingCount = this.pages.length - this.nextPageIndex;
    const items: ReadingItem[] = [];
    let nextChangeAt: number | null = null;
    if (this.active) {
      const { pages, expiresAt, protectedUntil } = this.active;
      for (const { cue, translatedText, pageIndex, pageCount } of pages) {
        items.push({ cue, kind: "translated", translatedText, pageIndex, pageCount, expiresAt });
      }
      nextChangeAt = pendingCount ? protectedUntil : expiresAt;
    } else {
      const latest = this.latest();
      // Live source text may fill an empty reader, but a completed translation must
      // only appear through its queued pages, never via this preview.
      if (latest && latest.translation.status !== "complete") {
        const expiresAt = (this.changedAt.get(latest.segment_id) ?? now) + SUBTITLE_VISIBLE_MS;
        if (expiresAt > readingTime) {
          items.push({ cue: latest, kind: "current", expiresAt });
          nextChangeAt = expiresAt;
        }
      }
    }
    return { items, nextChangeAt: visible ? nextChangeAt : null, pendingCount, historyVersion: this.historyVersion,
      completedCount: this.completed.size };
  }
}
