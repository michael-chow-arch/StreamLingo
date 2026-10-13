import { translationLanguages, type ExtensionSettings } from "../shared/config";
import { presentCue } from "./subtitle-presentation";
import { SUBTITLE_VISIBLE_MS, type ReadingItem, type ReadingWindow } from "./subtitle-store";
import { formatReadingProgress, formatStatus, t, type UiLanguage, type UiStatus } from "../shared/i18n";

interface CueNodes {
  readonly row: HTMLDivElement;
  readonly label: HTMLDivElement;
  readonly source: HTMLDivElement;
  readonly translated: HTMLDivElement;
}

export class SubtitleView {
  readonly host = document.createElement("div");
  private readonly root = this.host.attachShadow({ mode: "open" });
  private readonly panel = document.createElement("div");
  private readonly captions = document.createElement("div");
  private readonly status = document.createElement("div");
  private statusTimer: ReturnType<typeof setTimeout> | undefined;
  private disposed = false;
  private window: ReadingWindow | undefined;
  private readonly rows = new Map<string, CueNodes>();
  private statusValue: UiStatus | null = null;

  constructor(private readonly settings: ExtensionSettings, private language: UiLanguage = "zh-CN") {
    this.host.id = "streamlingo-subtitles";
    this.host.style.cssText = "position:absolute;inset:0;z-index:60;pointer-events:none;";
    const style = document.createElement("style");
    // Pagination budgets visible characters. Fold unusual blank lines visually
    // so they cannot turn one short page into an oversized column; keep the
    // source and translated textContent unchanged.
    style.textContent = `
      :host { font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif; color:white; container-type:size; }
      * { box-sizing:border-box; }
      .panel { position:absolute; bottom:12%; left:50%; transform:translateX(-50%); max-width:88%;
        width:max-content; min-width:160px; padding:9px 15px; border-radius:10px;
        background:rgba(10,15,24,.92); text-align:center; line-height:1.35; }
      .panel[hidden], [hidden] { display:none!important; }
      .cue + .cue { border-top:1px solid rgba(216,226,239,.25); margin-top:5px; padding-top:5px; }
      .cue-label { font-size:11px; color:#b8cee5; margin-bottom:3px; }
      .cue-label[data-mock="true"] { color:#fbd38d; }
      .source { font-size:min(.65em,3cqw,5cqh); line-height:1.25; color:#d8e2ef;
        overflow-wrap:anywhere; white-space:normal; }
      .translated { font-size:min(1em,4.2cqw,8cqh); font-weight:600;
        overflow-wrap:anywhere; white-space:normal; }
      .source + .translated:not([hidden]) { margin-top:3px; }
      .status { font-size:12px; color:#cbd5e1; overflow-wrap:anywhere; }
      .captions:not(:empty) + .status:not([hidden]) { margin-top:6px; }
      @container (max-height:400px) {
        .panel { padding:6px 10px; max-width:94%; }
        .cue-label { margin-bottom:1px; }
      }
    `;
    this.panel.className = "panel";
    this.panel.style.fontSize = `${Math.min(48, Math.max(16, settings.fontSizePx))}px`;
    this.panel.setAttribute("role", "region");
    this.panel.setAttribute("aria-label", t(language, "subtitleRegion"));
    this.host.lang = language;
    this.captions.className = "captions";
    this.status.className = "status";
    // One contextual live region avoids competing announcements for partial ASR
    // updates. Caption groups remain readable without repeatedly moving focus.
    this.status.setAttribute("role", "status");
    this.status.setAttribute("aria-atomic", "true");
    this.panel.append(this.captions, this.status);
    this.root.append(style, this.panel);
    this.setStatus({ key: "subtitleConnecting" });
  }

  setStatus(value: UiStatus): void {
    if (this.disposed) return;
    clearTimeout(this.statusTimer);
    this.statusValue = value;
    this.updateStatus();
    this.statusTimer = setTimeout(() => {
        this.statusValue = null;
        this.updateStatus();
    }, SUBTITLE_VISIBLE_MS);
  }

  setLanguage(language: UiLanguage): void {
    if (this.disposed || this.language === language) return;
    this.language = language;
    this.host.lang = language;
    this.panel.setAttribute("aria-label", t(language, "subtitleRegion"));
    // Update labels only. Keep the original caption and status expiry timers.
    if (this.window) this.render(this.window);
    else this.updateStatus();
  }

  render(window: ReadingWindow): void {
    if (this.disposed) return;
    this.window = window;
    const visible = window.items.slice(0, 2);
    const keys = new Set(visible.map((item) => this.itemKey(item)));
    for (const [key, nodes] of this.rows) {
      if (!keys.has(key)) {
        nodes.row.remove();
        this.rows.delete(key);
      }
    }
    visible.forEach((item, index) => {
      const key = this.itemKey(item);
      let nodes = this.rows.get(key);
      if (!nodes) {
        nodes = this.createRow(item);
        this.rows.set(key, nodes);
      }
      const { row, label, source, translated } = nodes;
      const fallback = translationLanguages(this.settings.translationMode);
      const sourceLanguage = item.cue.source_language ?? fallback.source;
      source.lang = sourceLanguage === "auto" ? "und" : sourceLanguage === "zh" ? "zh-CN" : "en";
      translated.lang = item.cue.target_language ?? fallback.target;
      const presentation = presentCue(item, this.settings.showSourceText, this.language);
      const labelText = index === 0 && item.kind === "translated" && item.pageIndex !== undefined && item.pageCount !== undefined
        ? `${presentation.label} · ${formatReadingProgress(this.language, item.pageIndex, item.pageCount, window.pendingCount)}`
        : presentation.label;
      row.dataset.hasTranslation = String(Boolean(presentation.translated));
      label.dataset.mock = String(presentation.isMock);
      if (label.textContent !== labelText) {
        label.textContent = labelText;
        row.setAttribute("aria-label", labelText);
      }
      if (source.textContent !== presentation.source) source.textContent = presentation.source;
      source.hidden = !presentation.showSource;
      if (translated.textContent !== presentation.translated) translated.textContent = presentation.translated;
      translated.hidden = !presentation.translated;
      // Keep existing translated elements connected while partial English or
      // another slot changes. Replacing the whole list interrupts reading.
      const existing = this.captions.children[index] ?? null;
      if (existing !== row) this.captions.insertBefore(row, existing);
    });
    this.updateStatus();
  }

  private itemKey(item: ReadingItem): string {
    return `${item.cue.session_id}:${item.kind}:${item.cue.segment_id}`;
  }

  private createRow(item: ReadingItem): CueNodes {
    const row = document.createElement("div");
    row.className = "cue";
    row.dataset.segmentId = String(item.cue.segment_id);
    row.dataset.kind = item.kind;
    row.setAttribute("role", "group");
    const label = document.createElement("div");
    label.className = "cue-label";
    const source = document.createElement("div");
    source.className = "source";
    const translated = document.createElement("div");
    translated.className = "translated";
    row.append(label, source, translated);
    return { row, label, source, translated };
  }

  private updateStatus(): void {
    const parts: string[] = [];
    if (this.statusValue) parts.push(formatStatus(this.language, this.statusValue));
    const value = parts.join(" · ");
    if (this.status.textContent !== value) this.status.textContent = value;
    this.status.hidden = value.length === 0;
    this.updateVisibility();
  }

  private updateVisibility(): void {
    this.panel.hidden = this.captions.childElementCount === 0 && this.status.hidden;
  }

  dispose(): void {
    this.disposed = true;
    this.window = undefined;
    this.rows.clear();
    this.statusValue = null;
    clearTimeout(this.statusTimer);
    this.captions.replaceChildren();
    this.status.textContent = "";
    this.status.hidden = true;
    this.panel.hidden = true;
    this.host.remove();
  }
}
