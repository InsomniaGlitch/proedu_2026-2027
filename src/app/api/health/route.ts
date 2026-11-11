export const dynamic = "force-dynamic";

/**
 * Проверка живости самого фронтенда. Не зависит от БД и Langflow —
 * состояние Langflow смотрите в /api/tutor/status.
 */
export async function GET() {
  return Response.json({ ok: true });
}
