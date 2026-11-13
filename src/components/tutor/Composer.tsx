"use client";

import { Send, Square } from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState, type KeyboardEvent } from "react";
import { MAX_MESSAGE_LENGTH } from "@/lib/tutor/constants";

interface Props {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  /** Меняется при смене чата — сбрасывает черновик */
  resetKey: string;
}

export interface ComposerHandle {
  focus: () => void;
}

export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { busy, onSend, onStop, resetKey },
  ref,
) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({ focus: () => textareaRef.current?.focus() }), []);

  // Автоматическая высота поля
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setValue("");
  }, [resetKey]);

  const trimmed = value.trim();
  const tooLong = value.length > MAX_MESSAGE_LENGTH;
  const canSend = !busy && trimmed.length > 0 && !tooLong;

  const submit = () => {
    if (!canSend) return;
    onSend(trimmed);
    setValue("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const showCounter = value.length > MAX_MESSAGE_LENGTH * 0.8;

  return (
    <div className="border-t border-slate-200/80 bg-white/70 px-3 pb-3 pt-3 sm:px-6">
      <div className="mx-auto max-w-3xl">
        <div
          className={`flex items-end gap-2 rounded-3xl border bg-white p-1.5 pl-4 shadow-sm transition focus-within:ring-4 ${
            tooLong
              ? "border-red-300 focus-within:ring-red-100"
              : "border-slate-200 focus-within:border-blue-400 focus-within:ring-blue-100"
          }`}
        >
          <label htmlFor="tutor-input" className="sr-only">
            Сообщение для Tutor
          </label>
          <textarea
            id="tutor-input"
            ref={textareaRef}
            value={value}
            rows={1}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Написать сообщение…"
            className="max-h-44 min-h-[40px] flex-1 resize-none bg-transparent py-2.5 text-[15px] leading-snug text-slate-900 outline-none placeholder:text-slate-400"
          />

          {busy ? (
            <button
              type="button"
              onClick={onStop}
              className="flex h-10 shrink-0 items-center gap-2 rounded-full bg-slate-800 px-4 text-sm font-semibold text-white transition hover:bg-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-800"
            >
              <Square className="size-3.5 fill-current" />
              <span className="max-sm:sr-only">Остановить</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={!canSend}
              className="flex h-10 shrink-0 items-center gap-2 rounded-full bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm shadow-blue-600/25 transition hover:bg-blue-700 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              <Send className="size-4" />
              <span className="max-sm:sr-only">Отправить</span>
            </button>
          )}
        </div>

        <div className="mt-2 flex items-start justify-between gap-3 px-2 text-xs text-slate-500">
          <p>
            Tutor может ошибаться — проверяйте важное по материалам курса. Он не выполняет задания за вас и не ставит оценки.
          </p>
          {showCounter && (
            <span className={`shrink-0 tabular-nums ${tooLong ? "font-semibold text-red-600" : ""}`}>
              {value.length}/{MAX_MESSAGE_LENGTH}
            </span>
          )}
        </div>
        {tooLong && (
          <p role="alert" className="mt-1 px-2 text-xs font-medium text-red-600">
            Сообщение слишком длинное — сократите его до {MAX_MESSAGE_LENGTH} символов.
          </p>
        )}
      </div>
    </div>
  );
});
