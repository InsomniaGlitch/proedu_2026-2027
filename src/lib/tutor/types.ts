/**
 * Общие типы модуля Tutor (используются и на клиенте, и на сервере).
 */

export type TutorErrorCode =
  | "bad_request" // некорректный ввод
  | "not_configured" // не задан TUTOR_FLOW_ID и т.п.
  | "unreachable" // Langflow недоступен
  | "timeout" // Langflow не ответил вовремя
  | "unauthorized" // неверный/отсутствующий API-ключ Langflow
  | "not_found" // flow не найден
  | "rate_limited" // слишком много запросов
  | "upstream" // ошибка внутри Langflow / модели / БД
  | "empty_response" // Langflow ответил, но текста нет
  | "network" // нет связи между браузером и приложением
  | "aborted" // пользователь остановил запрос
  | "interrupted" // страницу закрыли до получения ответа
  | "unknown";

export interface TutorErrorInfo {
  code: TutorErrorCode;
  /** Короткий заголовок для пользователя */
  message: string;
  /** Что делать дальше */
  hint?: string;
  retryable: boolean;
  /** Технические подробности (только если TUTOR_DEBUG=1) */
  detail?: string;
}

export type MessageStatus = "sending" | "sent" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  /** Только для сообщений пользователя */
  status?: MessageStatus;
  error?: TutorErrorInfo;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}

/**
 * Пользователь, от имени которого ведётся чат.
 * При объединении с авторизацией передайте сюда реального пользователя
 * (id используется для разделения историй и session_id в Langflow).
 */
export interface TutorUser {
  id: string;
  displayName?: string;
}

export type TutorServiceState = "checking" | "ready" | "not_configured" | "offline";

export interface TutorStatus {
  state: Exclude<TutorServiceState, "checking">;
  missing: string[];
}
