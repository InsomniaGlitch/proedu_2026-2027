"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { TutorServiceState, TutorStatus } from "../types";
import { fetchTutorStatus } from "./api";

const POLL_MS = 30_000;

/** Следит за доступностью Langflow и корректностью настроек. */
export function useTutorStatus() {
  const [state, setState] = useState<TutorServiceState>("checking");
  const [missing, setMissing] = useState<string[]>([]);
  const inFlight = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;

    try {
      const status: TutorStatus = await fetchTutorStatus(controller.signal);
      setState(status.state);
      setMissing(status.missing);
    } catch (error) {
      if ((error as Error)?.name === "AbortError") return;
      // Не достучались даже до собственного сервера — считаем сервис недоступным
      setState("offline");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("online", refresh);

    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("online", refresh);
      inFlight.current?.abort();
    };
  }, [refresh]);

  return { state, missing, refresh };
}
