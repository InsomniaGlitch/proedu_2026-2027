/**
 * Серверная конфигурация Tutor. Все значения берутся из .env
 * (см. .env.example). На клиент ничего из этого не попадает.
 */

export interface TutorConfig {
  baseUrl: string;
  apiKey: string | null;
  flowId: string | null;
  timeoutMs: number;
  /** "text" — обычный чат; "json" — формат guarded-flow из ветки main */
  inputMode: "text" | "json";
  debug: boolean;
}

function clean(value: string | undefined): string | null {
  const v = value?.trim();
  if (!v) return null;
  // Значения-заглушки из .env.example считаем «не заданными»
  if (/^YOUR_/i.test(v)) return null;
  return v;
}

export function getTutorConfig(): TutorConfig {
  const timeout = Number(process.env.TUTOR_REQUEST_TIMEOUT_MS);

  return {
    baseUrl: (clean(process.env.LANGFLOW_URL) ?? "http://127.0.0.1:7860").replace(/\/+$/, ""),
    apiKey: clean(process.env.LANGFLOW_API_KEY),
    flowId: clean(process.env.TUTOR_FLOW_ID),
    timeoutMs: Number.isFinite(timeout) && timeout >= 5000 ? timeout : 120_000,
    inputMode: process.env.TUTOR_INPUT_MODE === "json" ? "json" : "text",
    debug: process.env.TUTOR_DEBUG === "1",
  };
}
