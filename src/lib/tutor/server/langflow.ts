import { randomUUID } from "node:crypto";
import { makeError } from "../errors";
import type { TutorErrorInfo } from "../types";
import { getTutorConfig } from "./config";

export class TutorError extends Error {
  info: TutorErrorInfo;

  constructor(info: TutorErrorInfo) {
    super(info.message);
    this.name = "TutorError";
    this.info = info;
  }
}

interface AskParams {
  text: string;
  sessionId: string;
  userId?: string;
  /** Сигнал отмены (например, клиент закрыл вкладку) */
  signal?: AbortSignal;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

/**
 * Достаёт текст ответа из ответа Langflow.
 * Формат: outputs[].outputs[].results.message.text
 * В потоке несколько Chat Output (по веткам Smart Router) — выполнившаяся
 * ветка даёт непустой текст, остальные пустые, берём первый непустой.
 */
export function extractReply(body: unknown): string | null {
  const runs = asRecord(body)?.outputs;
  if (!Array.isArray(runs)) return null;

  for (const run of runs) {
    const outputs = asRecord(run)?.outputs;
    if (!Array.isArray(outputs)) continue;

    for (const output of outputs) {
      const out = asRecord(output);
      if (!out) continue;

      const message = asRecord(asRecord(out.results)?.message);
      const candidate =
        nonEmptyString(message?.text) ??
        nonEmptyString(asRecord(message?.data)?.text) ??
        nonEmptyString(asRecord(asRecord(out.outputs)?.message)?.message) ??
        nonEmptyString(asRecord(out.artifacts)?.message);

      if (candidate) return candidate;
    }
  }
  return null;
}

/** Убирает служебные строки, которые модель иногда пропускает в ответ. */
export function cleanReply(text: string): string {
  return text
    .replace(/^[ \t]*USED_SOURCES\s*:.*$/gim, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function extractDetail(raw: string): string {
  try {
    const json = JSON.parse(raw) as { detail?: unknown; message?: unknown };
    const d = json.detail ?? json.message;
    if (typeof d === "string") return d;
    if (d !== undefined) return JSON.stringify(d);
  } catch {
    // не JSON
  }
  return raw;
}

function truncate(text: string, max = 400): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export async function askLangflow({ text, sessionId, userId, signal }: AskParams) {
  const cfg = getTutorConfig();

  if (!cfg.flowId) {
    throw new TutorError(makeError("not_configured", { detail: "TUTOR_FLOW_ID is empty" }));
  }

  const inputValue =
    cfg.inputMode === "json"
      ? JSON.stringify({
          action: "ask",
          telegram_id: userId ?? null,
          run_id: randomUUID(),
          text,
        })
      : text;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (cfg.apiKey) headers["x-api-key"] = cfg.apiKey;

  const timeoutController = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    timeoutController.abort();
  }, cfg.timeoutMs);

  const combined = signal
    ? AbortSignal.any([timeoutController.signal, signal])
    : timeoutController.signal;

  const startedAt = Date.now();
  let status = 0;
  let raw = "";

  try {
    const response = await fetch(`${cfg.baseUrl}/api/v1/run/${encodeURIComponent(cfg.flowId)}`, {
      method: "POST",
      headers,
      cache: "no-store",
      signal: combined,
      body: JSON.stringify({
        input_value: inputValue,
        input_type: "chat",
        output_type: "chat",
        session_id: sessionId,
      }),
    });
    status = response.status;
    raw = await response.text();
  } catch (error) {
    if (timedOut) {
      throw new TutorError(makeError("timeout", { detail: `> ${cfg.timeoutMs} ms` }));
    }
    if (signal?.aborted) {
      throw new TutorError(makeError("aborted"));
    }
    const cause = (error as { cause?: { code?: string } })?.cause;
    throw new TutorError(
      makeError("unreachable", {
        detail: `${cfg.baseUrl}: ${cause?.code ?? (error as Error)?.message ?? "fetch failed"}`,
      }),
    );
  } finally {
    clearTimeout(timer);
  }

  if (status < 200 || status >= 300) {
    const detail = truncate(extractDetail(raw));
    console.error(`[tutor] Langflow responded ${status}: ${detail}`);

    if (status === 401 || status === 403) throw new TutorError(makeError("unauthorized", { detail }));
    if (status === 404) throw new TutorError(makeError("not_found", { detail }));
    if (status === 429) throw new TutorError(makeError("rate_limited", { detail }));
    throw new TutorError(makeError("upstream", { detail: `HTTP ${status}: ${detail}` }));
  }

  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    console.error("[tutor] Langflow returned non-JSON body");
    throw new TutorError(makeError("upstream", { detail: "Ответ Langflow не является JSON" }));
  }

  const reply = extractReply(body);
  const cleaned = reply ? cleanReply(reply) : "";

  if (!cleaned) {
    console.error("[tutor] Langflow returned no text in outputs");
    throw new TutorError(makeError("empty_response"));
  }

  return { reply: cleaned, durationMs: Date.now() - startedAt };
}
