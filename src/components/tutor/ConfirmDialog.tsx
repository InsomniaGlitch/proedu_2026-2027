"use client";

import { Trash2 } from "lucide-react";
import { useEffect, useRef } from "react";

interface Props {
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  onConfirm,
  onCancel,
}: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const onCancelRef = useRef(onCancel);

  useEffect(() => {
    onCancelRef.current = onCancel;
  }, [onCancel]);

  useEffect(() => {
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancelRef.current();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        aria-hidden="true"
        onClick={onCancel}
        className="tutor-fade-in absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]"
      />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-desc"
        className="tutor-pop relative w-full max-w-sm rounded-2xl bg-white p-5 shadow-2xl ring-1 ring-slate-900/5"
      >
        <span className="flex size-11 items-center justify-center rounded-xl bg-red-50 text-red-600 ring-1 ring-red-100">
          <Trash2 className="size-5" />
        </span>
        <h2
          id="confirm-title"
          className="mt-3 text-lg font-semibold text-slate-900"
        >
          {title}
        </h2>
        <p
          id="confirm-desc"
          className="mt-1 text-sm leading-relaxed text-slate-600"
        >
          {description}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            className="rounded-xl bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-200 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-red-600/25 transition hover:bg-red-700 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
