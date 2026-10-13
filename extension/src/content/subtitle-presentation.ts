import type { ReadingItem } from "./subtitle-store";
import { t, type UiLanguage } from "../shared/i18n";

export interface CuePresentation {
  readonly label: string;
  readonly source: string;
  readonly translated: string;
  readonly showSource: boolean;
  readonly isMock: boolean;
}

export function presentCue(item: ReadingItem, showSourceText: boolean, language: UiLanguage = "zh-CN"): CuePresentation {
  const cue = item.cue;
  // Only the reading queue may admit Chinese to the screen. A completed current
  // cue is still an English preview until the store promotes its own copy.
  const translation = item.kind === "translated" && cue.translation.status === "complete" ? cue.translation : null;
  const status = cue.translation.status;
  let label = t(language, item.kind === "translated" ? "cueTranslated" : "cueEnglish");
  if (translation?.is_mock) label += ` · ${t(language, "cueMock")}`;
  else if (status === "pending") label += ` · ${t(language, "cuePending")}`;
  else if (status === "error") label += ` · ${t(language, "cueError")}`;
  else if (status === "skipped") label += ` · ${t(language, "cueSkipped")}`;
  else if (!cue.source_final && !translation) label += ` · ${t(language, "cueRecognizing")}`;
  return {
    label,
    source: cue.source_text,
    translated: translation ? item.translatedText ?? translation.text : "",
    showSource: showSourceText || translation === null,
    isMock: translation?.is_mock ?? false,
  };
}
