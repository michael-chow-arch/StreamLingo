import type { TargetLanguage } from "@streamlingo/protocol";

export const MAX_TRANSLATION_PAGE_CHARACTERS = 48;
export const MAX_ENGLISH_PAGE_CHARACTERS = 120;

export function pageCapacity(language: TargetLanguage): number {
  return language === "en" ? MAX_ENGLISH_PAGE_CHARACTERS : MAX_TRANSLATION_PAGE_CHARACTERS;
}

export function pageCharacterCount(text: string, language: TargetLanguage): number {
  // Match visually collapsed whitespace while preserving the original payload.
  return language === "en" ? [...text.replace(/\s+/gu, " ")].length : visibleCharacterCount(text);
}

export function visibleCharacterCount(text: string): number {
  return [...text].filter((character) => !/\s/u.test(character)).length;
}

/** Preserve every original character; prefer sentence and native word boundaries. */
export function paginateTranslation(text: string, maxCharacters = MAX_TRANSLATION_PAGE_CHARACTERS,
  language: TargetLanguage = "zh-CN"): readonly string[] {
  if (!Number.isInteger(maxCharacters) || maxCharacters < 1) throw new RangeError("Page size must be a positive integer");
  if (!text) return [];
  const sentences = new Intl.Segmenter(language, { granularity: "sentence" });
  const words = new Intl.Segmenter(language, { granularity: "word" });
  const pages: string[] = [];
  let page = "";
  let count = 0;
  const flush = (): void => {
    if (page) pages.push(page);
    page = "";
    count = 0;
  };
  const append = (part: string): void => {
    const length = pageCharacterCount(part, language);
    if (count + length > maxCharacters) flush();
    page += part;
    count += length;
  };
  for (const { segment: sentence } of sentences.segment(text)) {
    if (pageCharacterCount(sentence, language) <= maxCharacters) {
      append(sentence);
      continue;
    }
    for (const { segment: word } of words.segment(sentence)) {
      if (pageCharacterCount(word, language) <= maxCharacters) append(word);
      else {
        // Very long identifiers/URLs can exceed a word boundary. Native string
        // iteration keeps surrogate pairs intact while enforcing the page cap.
        for (const character of word) append(character);
      }
    }
  }
  flush();
  return pages;
}
