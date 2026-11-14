"use client";
import {
  AlertTriangle,
  ChevronDown,
  CircleSlash,
  RotateCcw,
  Settings2,
  Trash2,
  WifiOff,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { errorTone } from "@/lib/tutor/errors";
import type { TutorErrorInfo } from "@/lib/tutor/types";

const TONES = {
  error: {
    box: "border-red-200 bg-red-50 text-red-900",
    icon: "bg-red-100 text-red-600",
    button:
      "bg-red-600 text-white hover:bg-red-700 focus-visible:outline-red-600",
    ghost: "text-red-700 hover:bg-red-100",
  },
  config: {
    box: "border-amber-200 bg-amber-50 text-amber-950",
    icon: "bg-amber-100 text-amber-600",
    button:
      "bg-amber-600 text-white hover:bg-amber-700 focus-visible:outline-amber-600",
    ghost: "text-amber-800 hover:bg-amber-100",
  },
  neutral: {
    box: "border-slate-200 bg-slate-50 text-slate-800",
    icon: "bg-slate-200 text-slate-600",
    button:
      "bg-slate-700 text-white hover:bg-slate-800 focus-visible:outline-slate-700",
    ghost: "text-slate-600 hover:bg-slate-200",
  },
} as const;

function iconFor(code: TutorErrorInfo["code"]): ReactNode {
  const cls = "size-4";
  switch (code) {
    case "network":
    case "unreachable":
      return <WifiOff className={cls} />;
    case "not_configured":
    case "unauthorized":
    case "not_found":
      return <Settings2 className={cls} />;
    case "aborted":
    case "interrupted":
      return <CircleSlash className={cls} />;
    default:
      return <AlertTriangle className={cls} />;
  }
}

interface Props {
  error: TutorErrorInfo;
  onRetry?: () => void;
  onDismiss?: () => void;
}

/** Дружелюбное уведомление об ошибке под сообщением пользователя. */
export function ErrorNotice({ error, onRetry, onDismiss }: Props) {
  const [open, setOpen] = useState(false);
  const tone = TONES[errorTone(error.code)];
  const showRetry = !!onRetry && error.retryable;

  return (
    <div
      role="alert"
      className={`tutor-fade-in rounded-xl border p-3 text-sm sm:rounded-2xl sm:p-3.5 ${tone.box}`}
    >
      <div className="flex gap-3">
        <span
          className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${tone.icon}`}
        >
          {iconFor(error.code)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold leading-snug">{error.message}</p>
          {error.hint && (
            <p className="mt-0.5 leading-relaxed opacity-90">{error.hint}</p>
          )}
          {error.detail && (
            <div className="mt-2">
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                className="inline-flex items-center gap-1 text-xs font-medium opacity-80 transition hover:opacity-100"
              >
                <ChevronDown
                  className={`size-3.5 transition ${open ? "rotate-180" : ""}`}
                />
                Технические детали
              </button>
              {open && (
                <pre className="mt-1.5 max-h-32 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-white/70 p-2 text-xs">
                  {error.detail}
                </pre>
              )}
            </div>
          )}
          {(showRetry || onDismiss) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {showRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold shadow-sm transition active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 ${tone.button}`}
                >
                  <RotateCcw className="size-3.5" />
                  Повторить
                </button>
              )}
              {onDismiss && (
                <button
                  type="button"
                  onClick={onDismiss}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition active:scale-95 ${tone.ghost}`}
                >
                  <Trash2 className="size-3.5" />
                  Удалить сообщение
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
