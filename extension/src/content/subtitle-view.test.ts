import assert from "node:assert/strict";
import test from "node:test";
import { DEFAULT_SETTINGS } from "../shared/config";
import type { ReadingItem, ReadingWindow } from "./subtitle-store";
import { SubtitleView } from "./subtitle-view";

class TestElement {
  readonly style: Record<string, string> = {};
  readonly dataset: Record<string, string> = {};
  readonly attributes = new Map<string, string>();
  children: TestElement[] = [];
  parentElement: TestElement | null = null;
  shadowRoot: TestElement | null = null;
  className = "";
  id = "";
  lang = "";
  private text: string | null = "";
  textWrites = 0;
  insertions = 0;
  removals = 0;
  get textContent(): string | null { return this.text; }
  set textContent(value: string | null) { this.text = value; this.textWrites++; }
  hidden = false;
  removed = false;
  get childElementCount(): number { return this.children.length; }
  append(...nodes: TestElement[]): void { for (const node of nodes) this.insertBefore(node, null); }
  insertBefore(node: TestElement, reference: TestElement | null): void {
    if (node === reference) return;
    if (node.parentElement) node.remove();
    const index = reference === null ? this.children.length : this.children.indexOf(reference);
    assert.ok(index >= 0);
    this.children.splice(index, 0, node);
    node.parentElement = this;
    node.removed = false;
    this.insertions++;
  }
  replaceChildren(...nodes: TestElement[]): void {
    for (const child of [...this.children]) child.remove();
    this.append(...nodes);
  }
  setAttribute(key: string, value: string): void { this.attributes.set(key, value); }
  attachShadow(): TestElement { this.shadowRoot = new TestElement(); return this.shadowRoot; }
  remove(): void {
    if (this.parentElement) {
      this.parentElement.children.splice(this.parentElement.children.indexOf(this), 1);
      this.parentElement = null;
    }
    this.removed = true;
    this.removals++;
  }
}

function installDocument(): () => void {
  const previous = Object.getOwnPropertyDescriptor(globalThis, "document");
  Object.defineProperty(globalThis, "document", { configurable: true, value: { createElement: () => new TestElement() } });
  return () => {
    if (previous) Object.defineProperty(globalThis, "document", previous);
    else Reflect.deleteProperty(globalThis, "document");
  };
}

function item(id = 1, kind: ReadingItem["kind"] = "translated", revision = 1): ReadingItem {
  return { kind, expiresAt: 12000, cue: {
    type: "subtitle", session_id: "session", segment_id: id, revision,
    start_ms: 0, end_ms: 1000, source_text: "This remains English.", source_final: true,
    translation: { status: "complete", text: "这仍然是中文。", is_mock: false },
  } };
}

function windowFor(items: readonly ReadingItem[], pendingCount = 0): ReadingWindow {
  return { items, pendingCount, nextChangeAt: null, historyVersion: 1, completedCount: items.length };
}

function find(root: TestElement, className: string): TestElement {
  for (const child of root.children) {
    if (child.className === className) return child;
    try { return find(child, className); } catch { /* Search the remaining siblings. */ }
  }
  throw new Error(`Element not found: ${className}`);
}

test("caption language attributes follow translation mode independently of UI language", () => {
  const restore = installDocument();
  const view = new SubtitleView({ ...DEFAULT_SETTINGS, translationMode: "zh-en" }, "zh-CN");
  const root = (view.host as unknown as TestElement).shadowRoot!;
  try {
    view.render(windowFor([item()]));
    assert.equal(find(root, "source").lang, "zh-CN");
    assert.equal(find(root, "translated").lang, "en");
    view.setLanguage("en");
    assert.equal(find(root, "source").lang, "zh-CN");
    const auto = { ...item(), cue: { ...item().cue, source_language: "auto" as const, target_language: "zh-CN" as const } };
    view.render(windowFor([auto]));
    assert.equal(find(root, "source").lang, "und");
    assert.equal(find(root, "translated").lang, "zh-CN");
  } finally { view.dispose(); restore(); }
});

test("live language changes preserve captions and original status expiry; dispose cannot resurrect them", (context) => {
  const restore = installDocument();
  context.mock.timers.enable({ apis: ["setTimeout"] });
  const view = new SubtitleView(DEFAULT_SETTINGS, "zh-CN");
  const host = view.host as unknown as TestElement;
  const root = host.shadowRoot!;
  try {
    view.render(windowFor([item()]));
    context.mock.timers.tick(6000);
    view.setLanguage("en");
    assert.equal(host.lang, "en");
    assert.equal(find(root, "cue-label").textContent, "Translated segment");
    assert.equal(find(root, "source").textContent, "This remains English.");
    assert.equal(find(root, "source").lang, "en");
    assert.equal(find(root, "translated").textContent, "这仍然是中文。");
    assert.equal(find(root, "translated").lang, "zh-CN");
    assert.equal(find(root, "status").textContent, "Connecting to the caption service…");
    context.mock.timers.tick(6000);
    assert.equal(find(root, "status").hidden, true, "Language switching must not extend the original timer");
    view.render(windowFor([]));
    view.setLanguage("zh-CN");
    assert.equal(find(root, "panel").hidden, true);
    assert.equal(find(root, "captions").childElementCount, 0);
    view.dispose();
    view.render(windowFor([item()]));
    view.setLanguage("en");
    view.setStatus({ key: "statusConnected" });
    assert.equal(host.removed, true);
    assert.equal(find(root, "captions").childElementCount, 0);
    assert.equal(find(root, "panel").hidden, true);
  } finally {
    view.dispose();
    restore();
  }
});

test("automatic page and queue updates reuse the reading row without mixing the next English segment", () => {
  const restore = installDocument();
  const view = new SubtitleView(DEFAULT_SETTINGS);
  const root = (view.host as unknown as TestElement).shadowRoot!;
  try {
    const first = { ...item(1), translatedText: "第一页。", pageIndex: 0, pageCount: 2 };
    view.render(windowFor([first], 2));
    const captions = find(root, "captions");
    const translatedRow = captions.children[0]!;
    const translatedText = find(translatedRow, "translated");
    const originalWrites = translatedText.textWrites;
    assert.equal(translatedText.textContent, "第一页。");
    assert.equal(find(root, "cue-label").textContent, "已译片段 · 第 1/2 页 · 待读 2 页");
    view.render(windowFor([first], 8));
    assert.equal(captions.children[0], translatedRow);
    assert.equal(translatedRow.parentElement, captions);
    assert.equal(translatedRow.removals, 0);
    assert.equal(translatedText.textWrites, originalWrites);
    assert.equal(captions.insertions, 1, "Updating a queue count must not reinsert the reading row");
    assert.equal(find(root, "cue-label").textContent, "已译片段 · 第 1/2 页 · 待读 8 页");
    view.setLanguage("en");
    assert.equal(captions.children[0], translatedRow);
    assert.equal(translatedText.textWrites, originalWrites, "Locale changes update UI labels, not the translated text node");
    assert.equal(find(root, "cue-label").textContent, "Translated segment · Page 1/2 · 8 pages queued");
    view.render(windowFor([{ ...first, translatedText: "第二页。", pageIndex: 1 }], 7));
    assert.equal(captions.children[0], translatedRow);
    assert.equal(translatedText.textContent, "第二页。");
    assert.equal(find(root, "source").textContent, first.cue.source_text, "English stays the actual source segment; it is not guessed per translated page");
    assert.equal(find(root, "cue-label").textContent, "Translated segment · Page 2/2 · 7 pages queued");
    view.render(windowFor([item(2, "current")]));
    assert.equal(find(root, "translated").textContent, "");
    assert.equal(find(root, "translated").hidden, true);
    assert.equal(captions.childElementCount, 1);
  } finally { view.dispose(); restore(); }
});

test("pagination is automatic, has no scrolling or interactive controls, and stop clears pending presentation", (context) => {
  const restore = installDocument();
  context.mock.timers.enable({ apis: ["setTimeout"] });
  const view = new SubtitleView(DEFAULT_SETTINGS);
  const root = (view.host as unknown as TestElement).shadowRoot!;
  try {
    const page = { ...item(), translatedText: "<b>完整文本</b>\n\n 空白仍留在文字中。", pageIndex: 0, pageCount: 3 };
    view.render(windowFor([page], 99));
    context.mock.timers.tick(12000);
    assert.equal(find(root, "status").hidden, true);
    assert.equal(find(root, "translated").textContent, page.translatedText, "Visual whitespace folding must not mutate the original caption text");
    assert.equal(find(root, "panel").hidden, false);
    const style = root.children[0]!.textContent!;
    assert.doesNotMatch(style, /line-clamp|overflow\s*:\s*(hidden|scroll|auto)|pointer-events\s*:\s*auto/);
    assert.match(style, /white-space:normal/);
    assert.doesNotMatch(style, /white-space:pre/);
    view.dispose();
    view.render(windowFor([page], 99));
    view.setLanguage("en");
    assert.equal(find(root, "panel").hidden, true);
    assert.equal(find(root, "captions").childElementCount, 0);
  } finally { view.dispose(); restore(); }
});

test("short automatic groups retain separate matching sources and show progress only once", () => {
  const restore = installDocument();
  const view = new SubtitleView(DEFAULT_SETTINGS);
  const root = (view.host as unknown as TestElement).shadowRoot!;
  try {
    const first = { ...item(1), translatedText: "第一句。", pageIndex: 0, pageCount: 1 };
    const second = { ...item(2), translatedText: "第二句。", pageIndex: 0, pageCount: 1,
      cue: { ...item(2).cue, source_text: "A different second sentence." } };
    view.render(windowFor([first, second], 4));
    const captions = find(root, "captions");
    assert.equal(captions.childElementCount, 2);
    const firstRow = captions.children[0]!;
    const secondRow = captions.children[1]!;
    assert.equal(find(firstRow, "source").textContent, first.cue.source_text);
    assert.equal(find(secondRow, "source").textContent, second.cue.source_text);
    assert.equal(find(firstRow, "translated").textContent, "第一句。");
    assert.equal(find(secondRow, "translated").textContent, "第二句。");
    assert.equal(find(firstRow, "cue-label").textContent, "已译片段 · 第 1/1 页 · 待读 4 页");
    assert.equal(find(secondRow, "cue-label").textContent, "已译片段");
    view.render(windowFor([first, second], 9));
    view.setLanguage("en");
    assert.equal(captions.children[0], firstRow);
    assert.equal(captions.children[1], secondRow);
    assert.equal(firstRow.removals, 0);
    assert.equal(secondRow.removals, 0);
    assert.equal(find(firstRow, "cue-label").textContent, "Translated segment · Page 1/1 · 9 pages queued");
    assert.equal(find(secondRow, "cue-label").textContent, "Translated segment");
  } finally { view.dispose(); restore(); }
});
