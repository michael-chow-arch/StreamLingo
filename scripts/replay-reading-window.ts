/** Offline only: node --import tsx scripts/replay-reading-window.ts [recording.json] [output-dir] */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseServerMessage, type SubtitleMessage } from "../packages/protocol/src/index";
import { SubtitleStore, readingDurationMs } from "../extension/src/content/subtitle-store";
import { presentCue } from "../extension/src/content/subtitle-presentation";

interface Arrival { atMs: number; cue: SubtitleMessage }
interface Exposure { key: string; id: number; text: string; shown: number; removed: number | null; budget: number }
function stats(values: number[]) {
  const v = [...values].sort((a, b) => a - b);
  return { min: v[0], p50: v[Math.max(0, Math.ceil(v.length * .5) - 1)],
    p95: v[Math.max(0, Math.ceil(v.length * .95) - 1)], max: v.at(-1) };
}
function replay(sessionId: string, arrivals: Arrival[]) {
  const store = new SubtitleStore(sessionId), received = new Map<number, Arrival>();
  const exposures: Exposure[] = [], issues: string[] = [], seen = new Set<string>();
  const active = new Map<string, Exposure>();
  let window = store.readingWindow(0);
  let now = 0, ticks = 0, maximumPendingPages = 0;
  function sample(at: number) {
    assert(at >= now); now = at; window = store.readingWindow(now);
    maximumPendingPages = Math.max(maximumPendingPages, window.pendingCount);
    assert(window.items.length <= 2, "At most two short captions per reading screen");
    const translated = window.items.filter(i => presentCue(i, false).translated);
    const keys = new Set(translated.map(i => `${i.cue.segment_id}:${i.pageIndex ?? 0}`));
    for (const [key, exposure] of active) {
      if (!keys.has(key)) {
        exposure.removed = now;
        if (now - exposure.shown < exposure.budget) issues.push(`Interrupted page ${key}`);
        active.delete(key);
      }
    }
    const combinedBudget = readingDurationMs(
      translated.map(i => presentCue(i, false).translated).join(" "),
      translated[0]?.cue.target_language ?? "zh-CN",
    );
    for (const item of translated) {
      const key = `${item.cue.segment_id}:${item.pageIndex ?? 0}`;
      const text = presentCue(item, false).translated;
      if (active.has(key) && active.get(key)!.text !== text) issues.push(`Changed visible text ${key}`);
      if (!active.has(key)) {
        if (seen.has(key)) issues.push(`Repeated page ${key}`);
        seen.add(key);
        const exposure = { key, id: item.cue.segment_id, text, shown: now, removed: null, budget: combinedBudget };
        active.set(key, exposure); exposures.push(exposure);
      }
    }
    if (window.nextChangeAt !== null) assert(window.nextChangeAt > now, "Timer advances");
  }
  function timersThrough(limit: number) {
    while (window.nextChangeAt !== null && window.nextChangeAt <= limit) {
      assert(++ticks < 100_000, "Timer drains"); sample(window.nextChangeAt);
    }
  }
  for (const a of arrivals) {
    timersThrough(a.atMs); store.upsert(a.cue, a.atMs);
    if (a.cue.translation.status === "complete" && !received.has(a.cue.segment_id)) received.set(a.cue.segment_id, a);
    sample(a.atMs);
  }
  timersThrough(Infinity);
  const waits: number[] = [], missing: number[] = [];
  for (const [id, arrival] of received) {
    const pages = exposures.filter(e => e.id === id);
    assert(arrival.cue.translation.status === "complete");
    if (!pages.length) missing.push(id);
    if (pages.map(p => p.text).join("") !== arrival.cue.translation.text) issues.push(`Lost or changed characters in ${id}`);
    if (pages[0]) waits.push(pages[0].shown - arrival.atMs);
  }
  if (store.completedValues().length !== received.size) issues.push("Discarded completed records");
  if (window.items.length || window.nextChangeAt !== null || window.pendingCount) issues.push("Queue did not drain");
  return { passed: !issues.length, issues, received: received.size, shown: received.size - missing.length,
    missing, pages: exposures.length, maximumPendingPages,
    pageDwellMs: stats(exposures.map(e => e.removed! - e.shown)),
    minimumDwellMarginMs: Math.min(...exposures.map(e => e.removed! - e.shown - e.budget)),
    additionalDisplayWaitMs: stats(waits), lastInputAtMs: arrivals.at(-1)?.atMs, drainedAtMs: now, exposures };
}
const inputPath = resolve(process.argv[2] ?? "output/regression-continuous/continuous-reviewed.json");
const outputDirectory = resolve(process.argv[3] ?? "output/no-drop-pagination");
const raw = readFileSync(inputPath, "utf8"), recording = JSON.parse(raw);
const arrivals: Arrival[] = recording.events.filter((e: Record<string, unknown>) => e.type === "subtitle")
  .map((event: Record<string, unknown>) => {
    const { received_after_s: seconds, stream_after_s: _streamAfter, ...message } = event;
    assert(typeof seconds === "number" && Number.isFinite(seconds) && seconds >= 0);
    const cue = parseServerMessage(message); assert(cue.type === "subtitle");
    return { atMs: Math.round(seconds * 1000), cue };
  });
const actual = replay(recording.session_id, arrivals), session = "10000000-0000-4000-8000-000000000001";
const stress = replay(session, Array.from({ length: 240 }, (_, i): Arrival => ({ atMs: i * 500, cue: {
  type: "subtitle", session_id: session, segment_id: i + 1, revision: 1, start_ms: i * 500, end_ms: i * 500 + 450,
  source_text: `Offline stress subtitle ${i + 1}`, source_final: true, translation: { status: "complete", is_mock: true,
    text: i % 3 === 0 ? `第${i + 1}条。${"这是用于离线验证长对话分页完整性的字幕。".repeat(5)}` : `离线压力字幕第${i + 1}条。` },
} })));
const hash = (text: string) => createHash("sha256").update(text).digest("hex");
const metadata = { generatedAtUtc: new Date().toISOString(), inputPath, inputSha256: hash(raw),
  implementationSha256: hash(readFileSync("extension/src/content/subtitle-store.ts", "utf8")),
  validationKind: "offline replay only, existing model output and separately synthetic pressure; no model or browser execution",
  method: "Run production store/presentation through every deadline to natural drain. Concatenate each segment's displayed pages and compare exactly with original translation. Stop controls excluded." };
mkdirSync(outputDirectory, { recursive: true });
for (const [name, result] of [["recorded-replay", actual], ["stress-replay", stress]] as const)
  writeFileSync(resolve(outputDirectory, `${name}.json`), JSON.stringify({ ...metadata, ...result }, null, 2) + "\n");
const compact = (result: typeof actual) => ({ ...result, exposures: undefined });
writeFileSync(resolve(outputDirectory, "summary.md"), "# Automatic subtitle pagination without dropping translations\n\n" +
  "Offline replay of existing real ASR/Qwen events and a separate synthetic pressure stream. Each displayed page must meet its reading duration; concatenating pages must reproduce the complete original text.\n\n" +
  "```json\n" + JSON.stringify({ actual: compact(actual), stress: compact(stress) }, null, 2) + "\n```\n\n" +
  "Sustained speech faster than the reading rate accumulates delay. Display wait excludes ASR and translation latency. No automatic catch-up discard.\n");
console.log(JSON.stringify({ outputDirectory, actual: compact(actual), stress: compact(stress) }, null, 2));
if (!actual.passed || !stress.passed) process.exitCode = 1;
