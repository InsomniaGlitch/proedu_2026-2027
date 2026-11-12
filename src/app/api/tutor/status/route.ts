import { getTutorConfig } from "@/lib/tutor/server/config";
import type { TutorStatus } from "@/lib/tutor/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * GET /api/tutor/status
 * Быстрая проверка: доступен ли Langflow и заполнены ли настройки.
 * Секреты не возвращаются.
 */
export async function GET() {
  const cfg = getTutorConfig();

  const missing: string[] = [];
  if (!cfg.flowId) missing.push("TUTOR_FLOW_ID");

  let langflowUp = false;
  try {
    const response = await fetch(`${cfg.baseUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    langflowUp = response.ok;
  } catch {
    langflowUp = false;
  }

  const status: TutorStatus = {
    state: !langflowUp ? "offline" : missing.length ? "not_configured" : "ready",
    missing,
  };

  return Response.json(status, { headers: { "Cache-Control": "no-store" } });
}
