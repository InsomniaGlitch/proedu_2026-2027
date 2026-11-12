import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "ИИ-помощник — Tutor",
  description: "ИИ-помощник по курсу «Устойчивое развитие: системный подход»",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="bg-gradient-to-br from-sky-50 via-white to-emerald-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
