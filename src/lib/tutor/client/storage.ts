import { DEFAULT_CHAT_TITLE, MAX_CHATS, MAX_MESSAGES_PER_CHAT } from "../constants";
import { makeError } from "../errors";
import type { ChatMessage, ChatSession, TutorUser } from "../types";
import { uid } from "./utils";

/**
 * Хранилище чатов — localStorage браузера, отдельно для каждого пользователя.
 * Весь доступ к хранилищу собран здесь: чтобы перейти на серверное
 * хранение (БД), достаточно заменить loadChats/saveChats.
 */

const KEY_PREFIX = "tutor.chats.v1.";
const USER_KEY = "tutor.anonymousUser.v1";

export function createChat(): ChatSession {
  const now = Date.now();
  return { id: uid(), title: DEFAULT_CHAT_TITLE, createdAt: now, updatedAt: now, messages: [] };
}

/** Анонимный пользователь, пока нет реальной авторизации. */
export function getAnonymousUser(): TutorUser {
  try {
    let id = localStorage.getItem(USER_KEY);
    if (!id) {
      id = uid();
      localStorage.setItem(USER_KEY, id);
    }
    return { id };
  } catch {
    return { id: "anonymous" };
  }
}

function isMessage(value: unknown): value is ChatMessage {
  const m = value as ChatMessage;
  return (
    !!m &&
    typeof m.id === "string" &&
    (m.role === "user" || m.role === "assistant") &&
    typeof m.content === "string" &&
    typeof m.createdAt === "number"
  );
}

function sanitizeChat(value: unknown): ChatSession | null {
  const c = value as ChatSession;
  if (!c || typeof c.id !== "string" || !Array.isArray(c.messages)) return null;

  const messages = c.messages.filter(isMessage).map((m): ChatMessage => {
    // Запрос был в полёте, когда страницу закрыли — показываем как прерванный
    if (m.role === "user" && m.status === "sending") {
      return { ...m, status: "error", error: makeError("interrupted") };
    }
    return m;
  });

  return {
    id: c.id,
    title: typeof c.title === "string" && c.title ? c.title : DEFAULT_CHAT_TITLE,
    createdAt: typeof c.createdAt === "number" ? c.createdAt : Date.now(),
    updatedAt: typeof c.updatedAt === "number" ? c.updatedAt : Date.now(),
    messages,
  };
}

export function loadChats(userId: string): { chats: ChatSession[]; activeId: string | null } {
  try {
    const raw = localStorage.getItem(KEY_PREFIX + userId);
    if (!raw) return { chats: [], activeId: null };

    const parsed = JSON.parse(raw) as { chats?: unknown[]; activeId?: string };
    const chats = (parsed.chats ?? [])
      .map(sanitizeChat)
      .filter((c): c is ChatSession => c !== null);

    const activeId = chats.some((c) => c.id === parsed.activeId) ? (parsed.activeId ?? null) : null;
    return { chats, activeId };
  } catch {
    return { chats: [], activeId: null };
  }
}

/** Возвращает false, если сохранить не удалось (квота, приватный режим). */
export function saveChats(userId: string, chats: ChatSession[], activeId: string | null): boolean {
  const trimmed = [...chats]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, MAX_CHATS)
    .map((c) => ({ ...c, messages: c.messages.slice(-MAX_MESSAGES_PER_CHAT) }));

  try {
    localStorage.setItem(KEY_PREFIX + userId, JSON.stringify({ chats: trimmed, activeId }));
    return true;
  } catch {
    return false;
  }
}
