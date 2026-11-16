import { makeError } from "../errors";
import type { TutorErrorInfo, TutorStatus } from "../types";

export class TutorClientError extends Error {
  info: TutorErrorInfo;

  constructor(info: TutorErrorInfo) {
    super(info.message);
    this.name = "TutorClientError";
    this.info = info;
  }
}

interface AskParams {
  message: string;
  sessionId: string;
  userId: string;
  signal?: AbortSignal;
}

export async function askTutor({ message, sessionId, userId, signal }: AskParams) {
  let response: Response;
  try {
    response = await fetch("/api/tutor/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, sessionId, userId }),
      signal,
    });
  } catch (error) {
    if ((error as Error)?.name === "AbortError") {
      throw new TutorClientError(makeError("aborted"));
    }
    throw new TutorClientError(makeError("network"));
  }

  let data: { reply?: string; durationMs?: number; error?: TutorErrorInfo } | null = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok || !data?.reply) {
    if (data?.error?.code) throw new TutorClientError(data.error);
    throw new TutorClientError(
      makeError(response.status >= 500 ? "upstream" : "unknown", {
        detail: `HTTP ${response.status}`,
      }),
    );
  }

  return { reply: data.reply, durationMs: data.durationMs ?? 0 };
}

export async function fetchTutorStatus(signal?: AbortSignal): Promise<TutorStatus> {
  const response = await fetch("/api/tutor/status", { cache: "no-store", signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as TutorStatus;
}
