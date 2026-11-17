/** uuid, работающий и в небезопасном контексте (http по IP в локальной сети). */
export function uid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/** session_id для Langflow: изолирует историю пользователя и конкретного чата. */
export function buildSessionId(userId: string, chatId: string): string {
  const safe = (s: string) => s.replace(/[^A-Za-z0-9_-]/g, "-");
  return `tutor_${safe(userId).slice(0, 36)}_${safe(chatId)}`.slice(0, 100);
}

const timeFormat = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });

export function formatTime(ts: number): string {
  return timeFormat.format(new Date(ts));
}

const dayFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });

export function formatDay(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOf(now) - startOf(d)) / 86_400_000);
  if (diffDays === 0) return "Сегодня";
  if (diffDays === 1) return "Вчера";
  return dayFormat.format(d);
}

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
