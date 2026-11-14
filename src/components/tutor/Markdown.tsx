"use client";

import { Check, Copy } from "lucide-react";
import { Children, isValidElement, memo, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

function nodeToText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeToText).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return nodeToText(node.props.children);
  return "";
}

function CodeBlock({ children }: { children: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const first = Children.toArray(children)[0];
  const className = isValidElement<{ className?: string }>(first) ? first.props.className : "";
  const language = /language-([\w-]+)/.exec(className ?? "")?.[1];

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(nodeToText(children).replace(/\n$/, ""));
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* буфер обмена недоступен */
    }
  };

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-slate-200 bg-slate-900 text-slate-100">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5 text-xs text-slate-400">
        <span>{language ?? "код"}</span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 transition hover:bg-white/10 hover:text-white focus-visible:outline-2 focus-visible:outline-blue-400"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? "Скопировано" : "Копировать"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-[13px] leading-relaxed">{children}</pre>
    </div>
  );
}

const components: Components = {
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-slate-950">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => (
    <ul className="my-2 list-disc space-y-1 pl-5 marker:text-blue-500">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 list-decimal space-y-1 pl-5 marker:font-medium marker:text-blue-600">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  h1: ({ children }) => <h3 className="mb-1 mt-4 text-lg font-semibold text-slate-950">{children}</h3>,
  h2: ({ children }) => <h3 className="mb-1 mt-4 text-base font-semibold text-slate-950">{children}</h3>,
  h3: ({ children }) => <h4 className="mb-1 mt-3 text-base font-semibold text-slate-950">{children}</h4>,
  h4: ({ children }) => <h4 className="mb-1 mt-3 font-semibold text-slate-950">{children}</h4>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-blue-700 underline decoration-blue-300 underline-offset-2 transition hover:text-blue-900 hover:decoration-blue-600"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-4 border-blue-300 bg-white/60 py-1 pl-3 text-slate-700">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-blue-200/70" />,
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  code: ({ className, children }) => {
    const isBlock = /language-/.test(className ?? "") || String(children).includes("\n");
    if (isBlock) return <code className={className}>{children}</code>;
    return (
      <code className="rounded-md bg-white/80 px-1.5 py-0.5 font-mono text-[0.85em] text-blue-900 ring-1 ring-blue-200/60">
        {children}
      </code>
    );
  },
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-xl border border-blue-200/70 bg-white/70">
      <table className="w-full border-collapse text-left text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-blue-100/60">{children}</thead>,
  th: ({ children }) => <th className="border-b border-blue-200/70 px-3 py-2 font-semibold">{children}</th>,
  td: ({ children }) => <td className="border-b border-blue-100 px-3 py-2 align-top">{children}</td>,
};

function MarkdownBase({ children }: { children: string }) {
  return (
    <div className="break-words text-[15px] leading-relaxed text-slate-800">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

/** Безопасный рендер markdown (сырой HTML не исполняется). */
export const Markdown = memo(MarkdownBase);
