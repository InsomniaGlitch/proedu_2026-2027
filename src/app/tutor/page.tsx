import type { Metadata } from "next";
import { TutorChat } from "@/components/tutor/TutorChat";
import { COURSE_NAME } from "@/lib/tutor/constants";

export const metadata: Metadata = {
  title: "Чат с ИИ-помощником (Tutor)",
  description: `Задайте вопрос по материалам курса «${COURSE_NAME}»`,
};

/**
 * Страница /tutor.
 * При объединении с остальными страницами достаточно оставить <TutorChat />
 * внутри общего layout (с сайдбаром, авторизацией и фоном) — компонент сам
 * занимает всю доступную высоту и ширину контейнера.
 */
export default function TutorPage() {
  return (
    <main className="mx-auto flex h-dvh w-full max-w-6xl flex-col gap-4 px-3 py-4 sm:px-6 sm:py-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-[#12285c] sm:text-3xl">
          Чат с ИИ-помощником (Tutor)
        </h1>
        <p className="mt-1 text-sm text-slate-600 sm:text-base">
          Задайте вопрос по материалам курса «{COURSE_NAME}»
        </p>
      </header>

      <div className="min-h-0 flex-1">
        <TutorChat />
      </div>
    </main>
  );
}
