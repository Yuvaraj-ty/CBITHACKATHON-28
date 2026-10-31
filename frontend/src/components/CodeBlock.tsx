import { useEffect, useRef, useState } from "react";
import { Highlight, type PrismTheme } from "prism-react-renderer";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export const atlasTheme: PrismTheme = {
  plain: { color: "#E2E8F0", backgroundColor: "transparent" },
  styles: [
    {
      types: ["comment", "prolog", "doctype", "cdata"],
      style: { color: "#64748B", fontStyle: "italic" },
    },
    {
      types: ["keyword", "builtin", "important", "atrule"],
      style: { color: "#C084FC" },
    },
    { types: ["function", "class-name"], style: { color: "#60A5FA" } },
    {
      types: ["string", "char", "attr-value", "regex", "inserted"],
      style: { color: "#34D399" },
    },
    { types: ["number", "boolean", "constant"], style: { color: "#FBBF24" } },
    {
      types: ["variable", "parameter", "deleted"],
      style: { color: "#F87171" },
    },
    { types: ["operator", "punctuation"], style: { color: "#94A3B8" } },
    { types: ["tag", "property", "selector"], style: { color: "#38BDF8" } },
  ],
};

const LANG_MAP: Record<string, string> = {
  python: "python",
  javascript: "jsx",
  typescript: "tsx",
  tsx: "tsx",
  c: "cpp",
  cpp: "cpp",
  java: "cpp",
  go: "go",
  json: "json",
  yaml: "yaml",
  markdown: "markdown",
  css: "css",
  markup: "markup",
  rust: "rust",
  kotlin: "kotlin",
  swift: "swift",
  sql: "sql",
  bash: "bash",
  text: "text",
  js: "jsx",
  ts: "tsx",
  py: "python",
};

export interface LineRange {
  start: number;
  end: number;
  tone?: "evidence" | "step" | "selection";
}

const TONE: Record<string, string> = {
  evidence: "bg-blue-500/10 shadow-[inset_2px_0_0_#3B82F6]",
  step: "bg-sky-400/15 shadow-[inset_2px_0_0_#38BDF8] animate-step-flash",
  selection: "bg-violet-500/15 shadow-[inset_2px_0_0_#8B5CF6]",
};

interface Props {
  code: string;
  language?: string | null;
  startLine?: number;
  ranges?: LineRange[];
  scrollTo?: { line: number; nonce: number } | null;
  onLineClick?: (line: number, shift: boolean) => void;
  copyable?: boolean;
  className?: string;
  testId?: string;
  wrap?: boolean;
}

export function CopyButton({
  text,
  label = "Copy",
  testId,
}: {
  text: string;
  label?: string;
  testId?: string;
}) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      data-testid={testId}
      title={label}
      onClick={(e) => {
        e.stopPropagation();
        void navigator.clipboard
          ?.writeText(text)
          .then(() => {
            setDone(true);
            toast.success(`${label} copied`);
            setTimeout(() => setDone(false), 1400);
          })
          .catch(() => toast.error("Clipboard unavailable"));
      }}
      className="inline-flex h-6 w-6 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
    >
      {done ? (
        <Check className="h-3.5 w-3.5 text-emerald-400" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

export function CodeBlock({
  code,
  language,
  startLine = 1,
  ranges = [],
  scrollTo,
  onLineClick,
  copyable = true,
  className,
  testId,
  wrap,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!scrollTo || !ref.current) return;
    const el = ref.current.querySelector<HTMLElement>(
      `[data-line="${scrollTo.line}"]`,
    );
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [scrollTo]);
  const lang = LANG_MAP[(language ?? "text").toLowerCase()] ?? "text";
  const toneFor = (n: number) => {
    let t: string | undefined;
    for (const r of ranges)
      if (n >= r.start && n <= r.end) t = r.tone ?? "evidence";
    return t;
  };
  return (
    <div
      data-testid={testId}
      className={cn(
        "group relative overflow-auto scroll-thin rounded-lg border border-line bg-editor font-mono text-[12.5px] leading-5",
        className,
      )}
      ref={ref}
    >
      {copyable && (
        <div className="sticky top-0 z-10 float-right m-1.5 opacity-0 transition-opacity group-hover:opacity-100">
          <CopyButton
            text={code}
            label="Code"
            testId={testId ? `${testId}-copy` : undefined}
          />
        </div>
      )}
      <Highlight
        theme={atlasTheme}
        code={code.replace(/\n$/, "")}
        language={lang}
      >
        {({ tokens, getLineProps, getTokenProps }) => (
          <pre
            className={cn("py-2", wrap && "whitespace-pre-wrap break-words")}
          >
            {tokens.map((line, i) => {
              const n = startLine + i;
              const tone = toneFor(n);
              const { className: lc, ...lp } = getLineProps({ line });
              return (
                <div
                  key={i}
                  {...lp}
                  data-line={n}
                  onClick={
                    onLineClick ? (e) => onLineClick(n, e.shiftKey) : undefined
                  }
                  className={cn(
                    lc,
                    "flex pr-4 transition-colors duration-150",
                    tone && TONE[tone],
                    onLineClick && "cursor-pointer hover:bg-slate-800/40",
                  )}
                >
                  <span className="sticky left-0 inline-block w-12 shrink-0 select-none bg-editor pr-3 text-right text-slate-600">
                    {n}
                  </span>
                  <span className="min-w-0">
                    {line.map((token, k) => (
                      <span key={k} {...getTokenProps({ token })} />
                    ))}
                  </span>
                </div>
              );
            })}
          </pre>
        )}
      </Highlight>
    </div>
  );
}
