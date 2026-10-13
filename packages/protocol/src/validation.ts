import { z } from "zod";
import type { HealthResponse, ServerMessage } from "./index";

const sessionId = z.string().uuid();
const nonnegative = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const positive = nonnegative.min(1);
const text = z.string().max(8000);
const mode = z.enum(["demo", "whisperlivekit"]);
const translationMode = z.enum(["disabled", "mock", "configured"]);
const sourceLanguage = z.enum(["en", "zh", "auto"]);
const targetLanguage = z.enum(["zh-CN", "en"]);

const healthSchema: z.ZodType<HealthResponse> = z.object({
  protocol_version: z.literal(1),
  mode,
  status: z.enum(["starting", "ready", "error"]),
  asr: z.enum(["loading", "ready", "error"]),
  translation: translationMode,
  source_languages: z.array(sourceLanguage).min(1).max(3).optional(),
  target_languages: z.array(targetLanguage).min(1).max(2).optional(),
}).strict();

const translation = z.discriminatedUnion("status", [
  z.object({ status: z.literal("disabled"), text: z.null() }).strict(),
  z.object({ status: z.literal("pending"), text: z.null() }).strict(),
  z.object({ status: z.literal("complete"), text: text.min(1), is_mock: z.boolean() }).strict(),
  z.object({ status: z.literal("error"), text: z.null() }).strict(),
  z.object({ status: z.literal("skipped"), text: z.null() }).strict(),
]);

const subtitle = z.object({
  type: z.literal("subtitle"),
  session_id: sessionId,
  segment_id: positive,
  revision: positive,
  start_ms: nonnegative,
  end_ms: nonnegative,
  source_text: text,
  source_final: z.boolean(),
  source_language: sourceLanguage.optional(),
  target_language: targetLanguage.optional(),
  translation,
}).strict().refine((value) => value.end_ms >= value.start_ms, "Invalid subtitle time range")
  .refine((value) => value.translation.status !== "complete" || value.source_final,
    "Only a final source can have a completed translation");

const messageSchema: z.ZodType<ServerMessage> = z.union([
  z.object({
    type: z.literal("ready"), protocol_version: z.literal(1), session_id: sessionId,
    mode, translation: translationMode, source_language: sourceLanguage.optional(), target_language: targetLanguage.optional(),
  }).strict(),
  subtitle,
  z.object({
    type: z.literal("error"), session_id: sessionId.nullable(), segment_id: positive.nullable(),
    code: z.enum(["INVALID_MESSAGE", "UNSUPPORTED_PROTOCOL", "UNSUPPORTED_LANGUAGE", "ASR_NOT_READY", "ASR_FAILED",
      "TRANSLATION_FAILED", "TRANSLATION_TIMEOUT", "TRANSLATION_BACKLOG", "AUDIO_BACKLOG",
      "SESSION_CONFLICT", "INTERNAL_ERROR"]),
    message: text, fatal: z.boolean(),
  }).strict(),
  z.object({
    type: z.literal("stopped"), session_id: sessionId, reason: z.enum(["user", "error"]),
  }).strict(),
]);

export function parseHealthResponse(input: unknown): HealthResponse {
  return healthSchema.parse(input);
}

export function parseServerMessage(input: unknown): ServerMessage {
  return messageSchema.parse(input);
}
