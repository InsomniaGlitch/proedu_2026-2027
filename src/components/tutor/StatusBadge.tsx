import type { TutorServiceState } from "@/lib/tutor/types";

const MAP: Record<TutorServiceState, { text: string; dot: string; box: string }> = {
  checking: { text: "Проверка…", dot: "bg-slate-400 animate-pulse", box: "bg-slate-100 text-slate-600" },
  ready: { text: "Tutor онлайн", dot: "bg-emerald-500", box: "bg-emerald-50 text-emerald-700" },
  not_configured: { text: "Требуется настройка", dot: "bg-amber-500", box: "bg-amber-50 text-amber-800" },
  offline: { text: "Нет связи", dot: "bg-red-500", box: "bg-red-50 text-red-700" },
};

export function StatusBadge({ state }: { state: TutorServiceState }) {
  const s = MAP[state];
  return (
    <span
      role="status"
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${s.box}`}
    >
      <span className={`size-2 rounded-full ${s.dot}`} aria-hidden="true" />
      {s.text}
    </span>
  );
}
