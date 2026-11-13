"use client";

import {
  Check,
  Loader2,
  MessageSquare,
  PanelLeftClose,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ChatSession } from "@/lib/tutor/types";
import { cn, formatDay } from "@/lib/tutor/client/utils";

interface Props {
  chats: ChatSession[];
  activeId: string | null;
  pendingIds: Set<string>;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}

function ChatRow({
  chat,
  active,
  pending,
  onSelect,
  onRename,
  onDelete,
}: {
  chat: ChatSession;
  active: boolean;
  pending: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(chat.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus({ preventScroll: true });
      inputRef.current?.select();
    }
  }, [editing]);

  const commit = () => {
    const title = draft.trim().slice(0, 60);
    if (title && title !== chat.title) onRename(title);
    setEditing(false);
  };

  const cancel = () => {
    setDraft(chat.title);
    setEditing(false);
  };

  if (editing) {
    return (
      <li className="relative my-0.5 rounded-xl border border-blue-500 bg-white p-1.5 shadow-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            commit();
          }}
          className="flex min-h-[38px] items-center gap-1"
        >
          <MessageSquare className="ml-1 size-4 shrink-0 text-blue-500" />
          <input
            ref={inputRef}
            value={draft}
            maxLength={60}
            aria-label="Название чата"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") cancel();
            }}
            className="min-w-0 flex-1 bg-transparent px-1.5 text-sm font-medium text-slate-800 outline-none placeholder:text-slate-400"
            placeholder="Название чата"
          />
          <button
            type="submit"
            aria-label="Сохранить"
            title="Сохранить (Enter)"
            className="rounded-lg p-1.5 text-emerald-600 transition hover:bg-emerald-50 active:scale-95"
          >
            <Check className="size-4" />
          </button>
          <button
            type="button"
            onClick={cancel}
            aria-label="Отмена"
            title="Отмена (Esc)"
            className="rounded-lg p-1.5 text-red-500 transition hover:bg-red-50 hover:text-red-600 active:scale-95"
          >
            <X className="size-4" />
          </button>
        </form>
      </li>
    );
  }

  return (
    <li className="group relative">
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? "true" : undefined}
        className={cn(
          "flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition focus-visible:outline-2 focus-visible:outline-blue-500",
          active
            ? "bg-blue-100/80 text-blue-900"
            : "text-slate-700 hover:bg-slate-200/60",
        )}
      >
        {pending ? (
          <Loader2
            className="size-4 shrink-0 animate-spin text-blue-600"
            aria-label="Идёт ответ"
          />
        ) : (
          <MessageSquare
            className={cn(
              "size-4 shrink-0",
              active ? "text-blue-600" : "text-slate-400",
            )}
          />
        )}
        <span className="min-w-0 flex-1 pr-12">
          <span className="block truncate text-sm font-medium">
            {chat.title}
          </span>
          <span className="block text-xs text-slate-500">
            {formatDay(chat.updatedAt)}
          </span>
        </span>
      </button>

      <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-0.5 rounded-lg bg-white/95 p-0.5 opacity-0 shadow-sm ring-1 ring-slate-200 transition group-focus-within:opacity-100 group-hover:opacity-100 max-lg:opacity-100">
        <button
          type="button"
          onClick={() => {
            setDraft(chat.title);
            setEditing(true);
          }}
          aria-label={`Переименовать чат «${chat.title}»`}
          className="rounded-md p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
        >
          <Pencil className="size-3.5" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          aria-label={`Удалить чат «${chat.title}»`}
          className="rounded-md p-1.5 text-slate-500 transition hover:bg-red-50 hover:text-red-600"
        >
          <Trash2 className="size-3.5" />
        </button>
      </div>
    </li>
  );
}

export function ChatSidebar({
  chats,
  activeId,
  pendingIds,
  onClose,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: Props) {
  const sorted = [...chats].sort((a, b) => b.updatedAt - a.updatedAt);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b border-slate-200/80 p-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onNew}
            className="flex min-w-0 flex-1 items-center justify-center gap-2 rounded-xl bg-blue-600 px-3.5 py-2.5 text-sm font-semibold text-white shadow-sm shadow-blue-600/20 transition hover:bg-blue-700 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            <Plus className="size-4 shrink-0" />
            <span className="truncate">Новый чат</span>
          </button>

          <button
            type="button"
            onClick={onClose}
            aria-label="Скрыть список чатов"
            className="flex size-10 shrink-0 items-center justify-center rounded-xl text-slate-600 transition hover:bg-slate-100 hover:text-slate-800 active:scale-95 focus-visible:outline-2 focus-visible:outline-blue-500 lg:hidden"
          >
            <PanelLeftClose className="size-5" />
          </button>
        </div>
      </div>

      <div className="px-4 pt-1 pb-1">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          История
        </p>
      </div>

      <nav
        aria-label="Список чатов"
        className="tutor-scroll min-h-0 flex-1 overflow-y-auto px-2 pb-3"
      >
        <ul className="space-y-1">
          {sorted.map((chat) => (
            <ChatRow
              key={chat.id}
              chat={chat}
              active={chat.id === activeId}
              pending={pendingIds.has(chat.id)}
              onSelect={() => onSelect(chat.id)}
              onRename={(title) => onRename(chat.id, title)}
              onDelete={() => onDelete(chat.id)}
            />
          ))}
        </ul>
      </nav>
    </div>
  );
}
