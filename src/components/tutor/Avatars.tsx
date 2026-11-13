import { Bot, User } from "lucide-react";

/**
 * Аватары собеседников. Стандартные иконки lucide-react —
 * чтобы заменить на фирменные, правьте только этот файл.
 */

export function BotAvatar({ className = "" }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`flex size-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 ring-1 ring-blue-200/70 sm:size-10 ${className}`}
    >
      <Bot className="size-5" strokeWidth={1.8} />
    </span>
  );
}

export function UserAvatar({ className = "" }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`flex size-9 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sky-700 ring-1 ring-sky-200/70 sm:size-10 ${className}`}
    >
      <User className="size-5" strokeWidth={1.8} />
    </span>
  );
}
