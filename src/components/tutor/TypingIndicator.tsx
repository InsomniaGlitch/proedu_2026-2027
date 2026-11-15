"use client";

import { useEffect, useState } from "react";
import { BotAvatar } from "./Avatars";

function label(seconds: number): string {
  if (seconds < 8) return "Tutor печатает…";
  if (seconds < 30) return "Ищу информацию в материалах курса…";
  if (seconds < 60) return "Подбираю ответ — это занимает чуть больше времени, чем обычно…";
  return "Ответ задерживается. Можно подождать ещё или остановить запрос.";
}

/** Индикатор ожидания ответа с пояснением, которое меняется со временем. */
export function TypingIndicator({ startedAt }: { startedAt: number }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const tick = () => setSeconds(Math.floor((Date.now() - startedAt) / 1000));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [startedAt]);

  return (
    <div className="tutor-fade-in flex items-start gap-3" role="status" aria-live="polite">
      <BotAvatar />
      <div className="rounded-2xl rounded-tl-md bg-[#e8effd] px-4 py-3 shadow-sm ring-1 ring-blue-200/60">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1" aria-hidden="true">
            <span className="tutor-dot size-2 rounded-full bg-blue-500" />
            <span className="tutor-dot size-2 rounded-full bg-blue-500" style={{ animationDelay: "0.15s" }} />
            <span className="tutor-dot size-2 rounded-full bg-blue-500" style={{ animationDelay: "0.3s" }} />
          </span>
          <span className="text-sm text-slate-600">{label(seconds)}</span>
        </div>
      </div>
    </div>
  );
}
