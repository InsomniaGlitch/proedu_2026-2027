import type { TutorErrorCode, TutorErrorInfo } from "./types";

type CatalogEntry = Pick<TutorErrorInfo, "message" | "hint" | "retryable">;

/** Каталог понятных пользователю сообщений об ошибках. */
const CATALOG: Record<TutorErrorCode, CatalogEntry> = {
  bad_request: {
    message: "Не удалось отправить сообщение",
    hint: "Проверьте текст сообщения и попробуйте снова.",
    retryable: false,
  },
  not_configured: {
    message: "Tutor ещё не настроен",
    hint: "Администратору нужно указать TUTOR_FLOW_ID в файле .env и перезапустить приложение.",
    retryable: true,
  },
  unreachable: {
    message: "Не удаётся связаться с Tutor",
    hint: "Похоже, сервис Langflow сейчас недоступен. Подождите немного и повторите запрос.",
    retryable: true,
  },
  timeout: {
    message: "Tutor слишком долго отвечает",
    hint: "Попробуйте повторить запрос или задать вопрос короче и конкретнее.",
    retryable: true,
  },
  unauthorized: {
    message: "Нет доступа к сервису Tutor",
    hint: "Проверьте LANGFLOW_API_KEY в файле .env (ключ создаётся в Langflow: Settings → Langflow API Keys).",
    retryable: true,
  },
  not_found: {
    message: "Сценарий Tutor не найден",
    hint: "Проверьте TUTOR_FLOW_ID в файле .env — ID виден в адресной строке открытого потока в Langflow.",
    retryable: true,
  },
  rate_limited: {
    message: "Слишком много запросов",
    hint: "Подождите несколько секунд и повторите.",
    retryable: true,
  },
  upstream: {
    message: "Tutor не смог обработать запрос",
    hint: "Это временная ошибка на стороне сервиса. Повторите попытку чуть позже.",
    retryable: true,
  },
  empty_response: {
    message: "Tutor вернул пустой ответ",
    hint: "Попробуйте переформулировать вопрос.",
    retryable: true,
  },
  network: {
    message: "Нет соединения",
    hint: "Проверьте подключение к интернету и повторите отправку.",
    retryable: true,
  },
  aborted: {
    message: "Ответ остановлен",
    hint: "Вы можете отправить вопрос ещё раз.",
    retryable: true,
  },
  interrupted: {
    message: "Запрос был прерван",
    hint: "Страница закрылась до получения ответа. Отправьте вопрос ещё раз.",
    retryable: true,
  },
  unknown: {
    message: "Что-то пошло не так",
    hint: "Повторите попытку. Если ошибка повторяется — сообщите администратору.",
    retryable: true,
  },
};

export function makeError(
  code: TutorErrorCode,
  options: { detail?: string; message?: string; hint?: string } = {},
): TutorErrorInfo {
  const base = CATALOG[code];
  return {
    code,
    message: options.message ?? base.message,
    hint: options.hint ?? base.hint,
    retryable: base.retryable,
    detail: options.detail,
  };
}

export type ErrorTone = "config" | "error" | "neutral";

/** Определяет визуальный тон уведомления об ошибке. */
export function errorTone(code: TutorErrorCode): ErrorTone {
  switch (code) {
    case "not_configured":
    case "unauthorized":
    case "not_found":
      return "config";
    case "aborted":
    case "interrupted":
      return "neutral";
    default:
      return "error";
  }
}

export const HTTP_STATUS_BY_CODE: Record<TutorErrorCode, number> = {
  bad_request: 400,
  not_configured: 503,
  unreachable: 502,
  timeout: 504,
  unauthorized: 502,
  not_found: 502,
  rate_limited: 429,
  upstream: 502,
  empty_response: 502,
  network: 502,
  aborted: 499,
  interrupted: 499,
  unknown: 500,
};
