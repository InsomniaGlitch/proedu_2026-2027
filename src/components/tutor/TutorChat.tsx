"use client";
import {
  ArrowDown,
  CheckCircle2,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Settings2,
  TriangleAlert,
  WifiOff,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { DEFAULT_CHAT_TITLE, GREETING } from "@/lib/tutor/constants";
import { makeError } from "@/lib/tutor/errors";
import { TutorClientError, askTutor } from "@/lib/tutor/client/api";
import {
  createChat,
  getAnonymousUser,
  loadChats,
  saveChats,
} from "@/lib/tutor/client/storage";
import { useTutorStatus } from "@/lib/tutor/client/useTutorStatus";
import { buildSessionId, cn, uid } from "@/lib/tutor/client/utils";
import type { ChatMessage, ChatSession, TutorUser } from "@/lib/tutor/types";
import { ChatSidebar } from "./ChatSidebar";
import { Composer, type ComposerHandle } from "./Composer";
import { ConfirmDialog } from "./ConfirmDialog";
import { ErrorNotice } from "./ErrorNotice";
import { MessageBubble } from "./MessageBubble";
import { StatusBadge } from "./StatusBadge";
import { TypingIndicator } from "./TypingIndicator";

export interface TutorChatProps {
  /**
   * Текущий пользователь. Если не передан — используется анонимный
   * идентификатор браузера. При интеграции с авторизацией передайте
   * сюда реального пользователя: от него зависят история чатов и session_id.
   */
  user?: TutorUser;
  className?: string;
}

interface Pending {
  messageId: string;
  startedAt: number;
}

interface ToastState {
  kind: "info" | "warning";
  text: string;
}

const PROMPT_HINTS = [
  "Объясни тему простыми словами",
  "Помоги разобраться в задаче",
  "С чего лучше начать?",
];

function titleFrom(text: string): string {
  const oneLine = text.replace(/\s+/g, " ").trim();
  return oneLine.length > 42 ? `${oneLine.slice(0, 42).trimEnd()}…` : oneLine;
}

export function TutorChat({ user, className }: TutorChatProps) {
  const externalUserId = user?.id;
  const [resolvedUser, setResolvedUser] = useState<TutorUser | null>(null);
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [pending, setPending] = useState<Record<string, Pending>>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [desktopOpen, setDesktopOpen] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<ChatSession | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [showJump, setShowJump] = useState(false);
  const {
    state: serviceState,
    missing,
    refresh: refreshStatus,
  } = useTutorStatus();

  const controllers = useRef(new Map<string, AbortController>());
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const composerRef = useRef<ComposerHandle>(null);
  const storageWarned = useRef(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---------- загрузка / сохранение ----------

  useEffect(() => {
    const u: TutorUser = externalUserId
      ? { id: externalUserId }
      : getAnonymousUser();
    const loaded = loadChats(u.id);
    let list = loaded.chats;
    let active = loaded.activeId;

    if (list.length === 0) {
      const fresh = createChat();
      list = [fresh];
      active = fresh.id;
    } else if (!active) {
      active = [...list].sort((a, b) => b.updatedAt - a.updatedAt)[0].id;
    }

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setResolvedUser(u);
    setChats(list);
    setActiveId(active);
    setHydrated(true);
  }, [externalUserId]);

  const showToast = (kind: ToastState["kind"], text: string) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ kind, text });
    toastTimer.current = setTimeout(() => setToast(null), 4500);
  };

  useEffect(() => {
    if (!hydrated || !resolvedUser) return;
    const timer = setTimeout(() => {
      const ok = saveChats(resolvedUser.id, chats, activeId);
      if (!ok && !storageWarned.current) {
        storageWarned.current = true;
        showToast(
          "warning",
          "Не удалось сохранить историю в браузере — после перезагрузки чаты могут пропасть.",
        );
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [chats, activeId, hydrated, resolvedUser]);

  // Прерываем запросы при уходе со страницы
  useEffect(() => {
    const map = controllers.current;
    return () => {
      map.forEach((c) => c.abort());
      map.clear();
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, []);

  // ---------- производные значения ----------

  const activeChat = useMemo(
    () => chats.find((c) => c.id === activeId) ?? null,
    [chats, activeId],
  );
  const activePending = activeId ? pending[activeId] : undefined;
  const pendingIds = useMemo(() => new Set(Object.keys(pending)), [pending]);
  const messages = activeChat?.messages ?? [];
  const lastMessage = messages[messages.length - 1];

  // ---------- прокрутка ----------

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    stickRef.current = true;
    el.scrollTo({ top: el.scrollHeight });
    setShowJump(false);
  }, [activeId, hydrated]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (stickRef.current || lastMessage?.role === "user") {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages.length, activePending, lastMessage?.role]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickRef.current = distance < 120;
    setShowJump(distance > 240);
  };

  const jumpToBottom = () => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  };

  // ---------- действия с чатами ----------

  const updateChat = (
    chatId: string,
    fn: (chat: ChatSession) => ChatSession,
  ) => {
    setChats((prev) => prev.map((c) => (c.id === chatId ? fn(c) : c)));
  };

  const selectChat = (id: string) => {
    setActiveId(id);
    setDrawerOpen(false);
    setTimeout(() => composerRef.current?.focus(), 50);
  };

  const newChat = () => {
    setDrawerOpen(false);
    // Пустой чат уже открыт — не плодим дубликаты
    if (activeChat && activeChat.messages.length === 0) {
      composerRef.current?.focus();
      return;
    }
    const fresh = createChat();
    setChats((prev) => [fresh, ...prev]);
    setActiveId(fresh.id);
    setTimeout(() => composerRef.current?.focus(), 50);
  };

  const renameChat = (id: string, title: string) => {
    updateChat(id, (c) => ({ ...c, title }));
  };

  const performDelete = (id: string) => {
    controllers.current.get(id)?.abort();
    const rest = chats.filter((c) => c.id !== id);
    if (rest.length === 0) {
      const fresh = createChat();
      setChats([fresh]);
      setActiveId(fresh.id);
    } else {
      setChats(rest);
      if (id === activeId) {
        setActiveId([...rest].sort((a, b) => b.updatedAt - a.updatedAt)[0].id);
      }
    }
    setDeleteTarget(null);
    showToast("info", "Чат удалён");
  };

  const requestDelete = (id: string) => {
    const chat = chats.find((c) => c.id === id);
    if (!chat) return;
    if (chat.messages.length === 0) performDelete(id);
    else setDeleteTarget(chat);
  };

  // ---------- отправка сообщений ----------

  const runRequest = async (
    chatId: string,
    userMessageId: string,
    text: string,
  ) => {
    if (!resolvedUser) return;
    const controller = new AbortController();
    controllers.current.set(chatId, controller);
    setPending((p) => ({
      ...p,
      [chatId]: { messageId: userMessageId, startedAt: Date.now() },
    }));
    try {
      const { reply } = await askTutor({
        message: text,
        sessionId: buildSessionId(resolvedUser.id, chatId),
        userId: resolvedUser.id,
        signal: controller.signal,
      });
      const answer: ChatMessage = {
        id: uid(),
        role: "assistant",
        content: reply,
        createdAt: Date.now(),
      };
      updateChat(chatId, (c) => ({
        ...c,
        updatedAt: Date.now(),
        messages: [
          ...c.messages.map((m) =>
            m.id === userMessageId
              ? { ...m, status: "sent" as const, error: undefined }
              : m,
          ),
          answer,
        ],
      }));
    } catch (error) {
      const info =
        error instanceof TutorClientError ? error.info : makeError("unknown");
      updateChat(chatId, (c) => ({
        ...c,
        updatedAt: Date.now(),
        messages: c.messages.map((m) =>
          m.id === userMessageId
            ? { ...m, status: "error" as const, error: info }
            : m,
        ),
      }));
      if (info.code !== "aborted") void refreshStatus();
    } finally {
      controllers.current.delete(chatId);
      setPending((p) => {
        const next = { ...p };
        delete next[chatId];
        return next;
      });
      setTimeout(() => composerRef.current?.focus(), 50);
    }
  };

  const sendMessage = (text: string) => {
    if (!activeChat || activePending) return;
    const message: ChatMessage = {
      id: uid(),
      role: "user",
      content: text,
      createdAt: Date.now(),
      status: "sending",
    };
    stickRef.current = true;
    updateChat(activeChat.id, (c) => ({
      ...c,
      title:
        c.messages.length === 0 && c.title === DEFAULT_CHAT_TITLE
          ? titleFrom(text)
          : c.title,
      updatedAt: Date.now(),
      messages: [...c.messages, message],
    }));
    void runRequest(activeChat.id, message.id, text);
  };

  const retryMessage = (messageId: string) => {
    if (!activeChat || activePending) return;
    const message = activeChat.messages.find((m) => m.id === messageId);
    if (!message) return;
    updateChat(activeChat.id, (c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.id === messageId
          ? { ...m, status: "sending" as const, error: undefined }
          : m,
      ),
    }));
    void runRequest(activeChat.id, messageId, message.content);
  };

  const editMessage = (messageId: string, text: string) => {
    if (!activeChat || activePending) return;
    const idx = activeChat.messages.findIndex((m) => m.id === messageId);
    if (idx === -1) return;
    const newText = text.trim();
    if (!newText) return;
    const chatId = activeChat.id;
    const oldTitleFromMessage = titleFrom(activeChat.messages[idx].content);
    stickRef.current = true;
    updateChat(chatId, (c) => ({
      ...c,
      title:
        idx === 0 && c.title === oldTitleFromMessage
          ? titleFrom(newText)
          : c.title,
      updatedAt: Date.now(),
      messages: c.messages
        .slice(0, idx + 1)
        .map((m) =>
          m.id === messageId
            ? {
                ...m,
                content: newText,
                status: "sending" as const,
                error: undefined,
              }
            : m,
        ),
    }));
    void runRequest(chatId, messageId, newText);
  };

  const regenerate = (assistantId: string) => {
    if (!activeChat || activePending) return;
    const idx = activeChat.messages.findIndex((m) => m.id === assistantId);
    if (idx === -1) return;
    const userMessage = activeChat.messages
      .slice(0, idx)
      .reverse()
      .find((m) => m.role === "user");
    if (!userMessage) return;
    updateChat(activeChat.id, (c) => ({
      ...c,
      messages: c.messages
        .filter((m) => m.id !== assistantId)
        .map((m) =>
          m.id === userMessage.id
            ? { ...m, status: "sending" as const, error: undefined }
            : m,
        ),
    }));
    void runRequest(activeChat.id, userMessage.id, userMessage.content);
  };

  const dismissMessage = (messageId: string) => {
    if (!activeChat) return;
    updateChat(activeChat.id, (c) => ({
      ...c,
      messages: c.messages.filter((m) => m.id !== messageId),
    }));
  };

  const stopRequest = () => {
    if (activeId) controllers.current.get(activeId)?.abort();
  };

  // ---------- разметка ----------

  const sidebar = (
    <ChatSidebar
      chats={chats}
      activeId={activeId}
      pendingIds={pendingIds}
      onClose={() => setDrawerOpen(false)}
      onSelect={selectChat}
      onNew={newChat}
      onRename={renameChat}
      onDelete={requestDelete}
    />
  );

  return (
    <section
      aria-label="Чат с Tutor"
      className={cn(
        "relative flex h-full min-h-[480px] overflow-hidden rounded-2xl border border-slate-200/80 bg-white/90 shadow-xl shadow-blue-900/5 backdrop-blur sm:rounded-3xl",
        className,
      )}
    >
      <div
        className={cn(
          "absolute inset-y-0 left-0 z-40 flex min-h-0 w-full flex-col bg-slate-50 transition-[transform,width,visibility] duration-300 ease-in-out",
          "lg:static lg:shrink-0 lg:overflow-hidden",
          drawerOpen ? "visible translate-x-0" : "invisible -translate-x-full",
          "lg:translate-x-0",
          desktopOpen ? "lg:visible lg:w-72" : "lg:invisible lg:w-0",
        )}
      >
        <div className="flex h-full w-full flex-col border-r border-slate-200/80 lg:w-72 lg:shrink-0">
          {sidebar}
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-slate-200/80 px-3 py-3 sm:px-5">
          <button
            type="button"
            onClick={() => setDrawerOpen((v) => !v)}
            aria-label={
              drawerOpen ? "Скрыть список чатов" : "Показать список чатов"
            }
            aria-expanded={drawerOpen}
            className="rounded-full p-2 text-slate-600 transition hover:bg-slate-100 lg:hidden"
          >
            {drawerOpen ? (
              <PanelLeftClose className="size-5" />
            ) : (
              <PanelLeftOpen className="size-5" />
            )}
          </button>
          <button
            type="button"
            onClick={() => setDesktopOpen((v) => !v)}
            aria-label={
              desktopOpen ? "Скрыть список чатов" : "Показать список чатов"
            }
            aria-expanded={desktopOpen}
            className="hidden rounded-full p-2 text-slate-600 transition hover:bg-slate-100 lg:flex"
          >
            {desktopOpen ? (
              <PanelLeftClose className="size-5" />
            ) : (
              <PanelLeftOpen className="size-5" />
            )}
          </button>
          <h2 className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-800 sm:text-base">
            {activeChat?.title ?? DEFAULT_CHAT_TITLE}
          </h2>
          <StatusBadge state={serviceState} />
        </header>

        {serviceState === "offline" && (
          <div
            role="alert"
            className="tutor-fade-in flex items-start gap-3 border-b border-red-100 bg-red-50 px-4 py-3 text-sm text-red-900 sm:px-6"
          >
            <WifiOff className="mt-0.5 size-4 shrink-0 text-red-600" />
            <p className="min-w-0 flex-1">
              <span className="font-semibold">Нет связи с сервисом Tutor.</span>{" "}
              Сообщения пока не уйдут. Мы будем проверять подключение
              автоматически.
            </p>
            <button
              type="button"
              onClick={() => void refreshStatus()}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs font-semibold text-red-700 shadow-sm ring-1 ring-red-200 transition hover:bg-red-100"
            >
              <RefreshCw className="size-3.5" />
              Проверить
            </button>
          </div>
        )}

        {serviceState === "not_configured" && (
          <div
            role="alert"
            className="tutor-fade-in flex items-start gap-3 border-b border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-950 sm:px-6"
          >
            <Settings2 className="mt-0.5 size-4 shrink-0 text-amber-600" />
            <p className="min-w-0 flex-1">
              <span className="font-semibold">Tutor не настроен.</span> Не
              заполнено:{" "}
              <code className="rounded bg-white/80 px-1 py-0.5 text-xs">
                {missing.join(", ") || ".env"}
              </code>
              . Укажите значение в файле{" "}
              <code className="rounded bg-white/80 px-1 py-0.5 text-xs">
                .env
              </code>{" "}
              и перезапустите приложение.
            </p>
            <button
              type="button"
              onClick={() => void refreshStatus()}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs font-semibold text-amber-800 shadow-sm ring-1 ring-amber-200 transition hover:bg-amber-100"
            >
              <RefreshCw className="size-3.5" />
              Проверить
            </button>
          </div>
        )}

        <div className="relative min-h-0 flex-1">
          <div
            ref={scrollRef}
            onScroll={onScroll}
            role="log"
            aria-live="polite"
            aria-label="История сообщений"
            className="tutor-scroll h-full overflow-y-auto px-3 py-6 sm:px-6"
          >
            {!hydrated || !activeChat ? (
              <div
                className="mx-auto flex max-w-3xl flex-col gap-5"
                aria-busy="true"
              >
                {[0, 1].map((i) => (
                  <div key={i} className="flex gap-3">
                    <div className="size-10 shrink-0 animate-pulse rounded-full bg-slate-200" />
                    <div className="h-20 w-2/3 animate-pulse rounded-2xl bg-slate-100" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="mx-auto flex max-w-3xl flex-col gap-5">
                <MessageBubble
                  role="assistant"
                  content={GREETING}
                  createdAt={activeChat.createdAt}
                />
                {messages.length === 0 && (
                  <div className="tutor-fade-in pl-12 sm:pl-[52px]">
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                      С чего начать
                    </p>
                    <div className="flex flex-col items-start gap-2">
                      {PROMPT_HINTS.map((hint) => (
                        <button
                          key={hint}
                          type="button"
                          onClick={() => sendMessage(hint)}
                          disabled={!!activePending}
                          className="rounded-xl border border-blue-200 bg-white px-3.5 py-2 text-left text-sm text-blue-800 shadow-sm transition hover:border-blue-300 hover:bg-blue-50 disabled:opacity-50"
                        >
                          {hint}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((m) => (
                  <MessageBubble
                    key={m.id}
                    role={m.role}
                    content={m.content}
                    createdAt={m.createdAt}
                    status={m.status}
                    canRegenerate={
                      !activePending &&
                      m.role === "assistant" &&
                      m.id === lastMessage?.id
                    }
                    onRegenerate={() => regenerate(m.id)}
                    canEdit={!activePending && m.role === "user"}
                    onEdit={(text) => editMessage(m.id, text)}
                    footer={
                      m.status === "error" && m.error ? (
                        <ErrorNotice
                          error={m.error}
                          onRetry={
                            activePending ? undefined : () => retryMessage(m.id)
                          }
                          onDismiss={() => dismissMessage(m.id)}
                        />
                      ) : undefined
                    }
                  />
                ))}
                {activePending && (
                  <TypingIndicator startedAt={activePending.startedAt} />
                )}
              </div>
            )}
          </div>
          {showJump && (
            <button
              type="button"
              onClick={jumpToBottom}
              aria-label="Прокрутить к последнему сообщению"
              className="tutor-fade-in absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-white px-3.5 py-2 text-xs font-medium text-slate-700 shadow-lg ring-1 ring-slate-200 transition hover:bg-slate-50"
            >
              <ArrowDown className="size-3.5" />
              Вниз
            </button>
          )}
        </div>

        <Composer
          ref={composerRef}
          busy={!!activePending}
          onSend={sendMessage}
          onStop={stopRequest}
          resetKey={activeId ?? ""}
        />
      </div>

      {toast && (
        <div
          role="status"
          className={cn(
            "tutor-pop pointer-events-none absolute bottom-24 left-1/2 z-40 flex max-w-[90%] -translate-x-1/2 items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium shadow-lg",
            toast.kind === "warning"
              ? "bg-amber-500 text-white"
              : "bg-slate-800 text-white",
          )}
        >
          {toast.kind === "warning" ? (
            <TriangleAlert className="size-4 shrink-0" />
          ) : (
            <CheckCircle2 className="size-4 shrink-0" />
          )}
          {toast.text}
        </div>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Удалить чат?"
          description={`Чат «${deleteTarget.title}» и вся его переписка будут удалены без возможности восстановления.`}
          confirmLabel="Удалить"
          onConfirm={() => performDelete(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </section>
  );
}
