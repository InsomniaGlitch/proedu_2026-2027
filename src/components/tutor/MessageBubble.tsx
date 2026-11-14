"use client";
import {
  AlertCircle,
  Check,
  CheckCheck,
  Clock,
  Copy,
  Pencil,
  RotateCw,
  X,
} from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import type { ChatMessage } from "@/lib/tutor/types";
import { formatTime } from "@/lib/tutor/client/utils";
import { BotAvatar, UserAvatar } from "./Avatars";
import { Markdown } from "./Markdown";

interface Props {
  role: ChatMessage["role"];
  content: string;
  createdAt: number;
  status?: ChatMessage["status"];
  /** Дополнительный блок под сообщением (например, ошибка) */
  footer?: ReactNode;
  canRegenerate?: boolean;
  onRegenerate?: () => void;
  canEdit?: boolean;
  onEdit?: (text: string) => void;
}

function StatusIcon({ status }: { status?: ChatMessage["status"] }) {
  if (status === "sending") {
    return (
      <Clock className="size-3.5 text-slate-400" aria-label="Отправляется" />
    );
  }
  if (status === "error") {
    return (
      <AlertCircle
        className="size-3.5 text-red-500"
        aria-label="Не отправлено"
      />
    );
  }
  if (status === "sent") {
    return (
      <CheckCheck className="size-3.5 text-blue-500" aria-label="Доставлено" />
    );
  }
  return null;
}

const actionButtonClass =
  "flex size-7 shrink-0 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 active:scale-95 focus-visible:outline-2 focus-visible:outline-blue-500";

function MessageEditor({
  initial,
  onSave,
  onCancel,
}: {
  initial: string;
  onSave: (text: string) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const ref = useRef<HTMLTextAreaElement>(null);
  const trimmed = draft.trim();
  const canSave = trimmed.length > 0 && trimmed !== initial.trim();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft]);

  const save = () => {
    if (canSave) onSave(trimmed);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Escape") {
      onCancel();
    } else if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      save();
    }
  };

  return (
    <div className="w-full rounded-xl bg-white p-2 shadow-sm ring-2 ring-emerald-300 sm:rounded-2xl">
      <textarea
        ref={ref}
        rows={1}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        aria-label="Редактирование сообщения"
        className="block max-h-60 w-full resize-none bg-transparent px-2 py-1 text-[15px] leading-relaxed text-slate-900 outline-none"
      />
      <div className="mt-1 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-slate-600 transition hover:bg-slate-100 active:scale-95"
        >
          <X className="size-3.5" />
          Отмена
        </button>
        <button
          type="button"
          onClick={save}
          disabled={!canSave}
          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-700 active:scale-95 disabled:opacity-50 disabled:active:scale-100"
        >
          <Check className="size-3.5" />
          Отправить
        </button>
      </div>
    </div>
  );
}

export function MessageBubble({
  role,
  content,
  createdAt,
  status,
  footer,
  canRegenerate = false,
  onRegenerate,
  canEdit = false,
  onEdit,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const isUser = role === "user";
  const showEditor = isUser && editing;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* буфер обмена недоступен */
    }
  };

  return (
    <div
      className={`tutor-fade-in flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}
    >
      {isUser ? <UserAvatar /> : <BotAvatar />}
      <div
        className={`flex min-w-0 max-w-[88%] flex-col sm:max-w-[78%] ${isUser ? "items-end" : "items-start"} ${
          showEditor ? "w-full" : ""
        }`}
      >
        {showEditor ? (
          <MessageEditor
            initial={content}
            onCancel={() => setEditing(false)}
            onSave={(text) => {
              setEditing(false);
              onEdit?.(text);
            }}
          />
        ) : (
          <div
            className={
              isUser
                ? "rounded-xl rounded-tr-sm bg-[#dcf3e4] px-4 py-2.5 text-[15px] leading-relaxed text-slate-900 shadow-sm ring-1 ring-emerald-200/60 sm:rounded-2xl sm:rounded-tr-md"
                : "rounded-xl rounded-tl-sm bg-[#e8effd] px-4 py-3 shadow-sm ring-1 ring-blue-200/60 sm:rounded-2xl sm:rounded-tl-md"
            }
          >
            {isUser ? (
              <p className="whitespace-pre-wrap break-words">{content}</p>
            ) : (
              <Markdown>{content}</Markdown>
            )}
          </div>
        )}
        {!showEditor && (
          <div
            className={`mt-1 flex w-full items-center gap-1 px-1 text-xs text-slate-500 ${
              isUser ? "justify-end" : ""
            }`}
          >
            <time dateTime={new Date(createdAt).toISOString()}>
              {formatTime(createdAt)}
            </time>
            {isUser && <StatusIcon status={status} />}
            {!isUser && (
              <div className="ml-auto flex items-center gap-0.5">
                <button
                  type="button"
                  onClick={copy}
                  aria-label={copied ? "Скопировано" : "Скопировать ответ"}
                  title={copied ? "Скопировано" : "Скопировать ответ"}
                  className={actionButtonClass}
                >
                  {copied ? (
                    <Check className="size-4 text-emerald-600" />
                  ) : (
                    <Copy className="size-4" />
                  )}
                </button>
                {canRegenerate && onRegenerate && (
                  <button
                    type="button"
                    onClick={onRegenerate}
                    aria-label="Сгенерировать ответ заново"
                    title="Сгенерировать заново"
                    className={actionButtonClass}
                  >
                    <RotateCw className="size-4" />
                  </button>
                )}
              </div>
            )}
            {isUser && canEdit && onEdit && (
              <button
                type="button"
                onClick={() => setEditing(true)}
                aria-label="Редактировать сообщение"
                title="Редактировать"
                className={actionButtonClass}
              >
                <Pencil className="size-4" />
              </button>
            )}
          </div>
        )}
        {footer && <div className="mt-2 w-full">{footer}</div>}
      </div>
    </div>
  );
}
