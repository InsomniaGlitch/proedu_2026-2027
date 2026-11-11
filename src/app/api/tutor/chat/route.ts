import { HTTP_STATUS_BY_CODE, makeError } from "@/lib/tutor/errors";
import { MAX_MESSAGE_LENGTH } from "@/lib/tutor/constants";
import { getTutorConfig } from "@/lib/tutor/server/config";
import { TutorError, askLangflow } from "@/lib/tutor/server/langflow";
import type { TutorErrorInfo } from "@/lib/tutor/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const SESSION_RE = /^[A-Za-z0-9_-]{8,100}$/;

function errorResponse(info: TutorErrorInfo) {
  const debug = getTutorConfig().debug;
  const payload = debug ? info : { ...info, detail: undefined };
  return Response.json({ error: payload }, { status: HTTP_STATUS_BY_CODE[info.code] });
}

/**
 * POST /api/tutor/chat
 * body: { message: string, sessionId: string, userId?: string }
 * ok:   { reply: string, durationMs: number }
 * err:  { error: TutorErrorInfo }
 */
export async function POST(request: Request) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse(makeError("bad_request", { detail: "Invalid JSON" }));
  }

  const message = typeof body.message === "string" ? body.message.trim() : "";
  const sessionId = typeof body.sessionId === "string" ? body.sessionId : "";
  const userId = typeof body.userId === "string" ? body.userId.slice(0, 100) : undefined;

  if (!message) {
    return errorResponse(
      makeError("bad_request", { message: "Сообщение пустое", hint: "Напишите вопрос и отправьте снова." }),
    );
  }
  if (message.length > MAX_MESSAGE_LENGTH) {
    return errorResponse(
      makeError("bad_request", {
        message: "Сообщение слишком длинное",
        hint: `Сократите текст до ${MAX_MESSAGE_LENGTH} символов или разбейте вопрос на части.`,
      }),
    );
  }
  if (!SESSION_RE.test(sessionId)) {
    return errorResponse(makeError("bad_request", { detail: "Invalid sessionId" }));
  }

  try {
    const result = await askLangflow({
      text: message,
      sessionId,
      userId,
      signal: request.signal,
    });
    return Response.json(result);
  } catch (error) {
    if (error instanceof TutorError) return errorResponse(error.info);
    console.error("[tutor] Unexpected error:", error);
    return errorResponse(makeError("unknown", { detail: (error as Error)?.message }));
  }
}
