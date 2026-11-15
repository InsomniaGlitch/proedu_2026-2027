"use client";

import { RefreshCw, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/tutor/client/utils";

type Tone = "error" | "warning";

const tones: Record<
  Tone,
  { box: string; iconWrap: string; title: string; text: string; button: string }
> = {
  error: {
    box: "border-red-200/70 bg-gradient-to-br from-red-50 to-white",
    iconWrap: "bg-red-100 text-red-600 ring-1 ring-red-200/70",
    title: "text-red-950",
    text: "text-red-900/75",
    button: "bg-white text-red-700 ring-1 ring-red-200 hover:bg-red-50",
  },
  warning: {
    box: "border-amber-200/70 bg-gradient-to-br from-amber-50 to-white",
    iconWrap: "bg-amber-100 text-amber-600 ring-1 ring-amber-200/70",
    title: "text-amber-950",
    text: "text-amber-900/75",
    button: "bg-white text-amber-800 ring-1 ring-amber-200 hover:bg-amber-50",
  },
};

interface Props {
  tone: Tone;
  icon: LucideIcon;
  title: string;
  children: ReactNode;
  actionLabel?: string;
  onAction?: () => void;
}

export function ServiceNotice({
  tone,
  icon: Icon,
  title,
  children,
  actionLabel,
  onAction,
}: Props) {
  const t = tones[tone];

  return (
    <div
      role="alert"
      className={cn(
        "tutor-fade-in mx-3 mt-3 flex items-start gap-3 rounded-2xl border p-3.5 shadow-sm sm:mx-6",
        t.box,
      )}
    >
      <span
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-xl",
          t.iconWrap,
        )}
      >
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className={cn("text-sm font-semibold", t.title)}>{title}</p>
        <div className={cn("mt-0.5 text-sm leading-relaxed", t.text)}>
          {children}
        </div>
        {actionLabel && onAction && (
          <button
            type="button"
            onClick={onAction}
            className={cn(
              "mt-2.5 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold shadow-sm transition active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500",
              t.button,
            )}
          >
            <RefreshCw className="size-3.5" />
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}
