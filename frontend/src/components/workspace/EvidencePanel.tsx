import { useNavigate } from "react-router-dom";
import {
  Crosshair,
  FileSearch,
  Info,
  MousePointerSquareDashed,
  Network,
} from "lucide-react";
import { useApp } from "@/lib/appState";
import type { Confidence, Evidence } from "@/lib/types";
import { cn } from "@/lib/utils";
import { CodeBlock, CopyButton } from "@/components/CodeBlock";

const LEVEL: Record<string, { label: string; color: string; bar: string }> = {
  high: {
    label: "High evidence quality",
    color: "text-emerald-300",
    bar: "bg-emerald-500",
  },
  medium: {
    label: "Medium evidence quality",
    color: "text-amber-300",
    bar: "bg-amber-500",
  },
  low: {
    label: "Low evidence quality",
    color: "text-orange-300",
    bar: "bg-orange-500",
  },
  insufficient: {
    label: "Insufficient evidence",
    color: "text-red-300",
    bar: "bg-red-500",
  },
  selected: {
    label: "Your selection",
    color: "text-violet-300",
    bar: "bg-violet-500",
  },
  file: { label: "Scoped to file", color: "text-sky-300", bar: "bg-sky-500" },
};

export function ConfidenceMeter({
  c,
  compact,
}: {
  c: Confidence;
  compact?: boolean;
}) {
  const l = LEVEL[c.level] ?? LEVEL.low;
  return (
    <div
      data-testid="evidence-confidence"
      className={cn(
        !compact && "rounded-lg border border-line bg-panel/60 p-3",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className={cn("text-[12px] font-medium", l.color)}>
          {l.label}
        </span>
        <span className="font-mono text-[11px] text-slate-500">
          {Math.round(c.score * 100)}%
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500",
            l.bar,
          )}
          style={{ width: `${Math.max(4, c.score * 100)}%` }}
        />
      </div>
      {!compact && (
        <>
          {Object.keys(c.factors).length > 0 && (
            <div className="mt-2.5 grid grid-cols-5 gap-1.5">
              {Object.entries(c.factors).map(([k, v]) => (
                <div key={k} title={k} className="text-center">
                  <div className="mx-auto h-8 w-1.5 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="mt-auto w-full rounded-full bg-blue-500/80"
                      style={{
                        height: `${v * 100}%`,
                        marginTop: `${(1 - v) * 100}%`,
                      }}
                    />
                  </div>
                  <p className="mt-1 text-[9.5px] capitalize text-slate-500">
                    {k}
                  </p>
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 flex gap-1.5 text-[11px] leading-snug text-slate-500">
            <Info className="mt-[1px] h-3 w-3 shrink-0" />
            {c.note}
          </p>
        </>
      )}
    </div>
  );
}

export function EvidencePanel({
  evidence,
  confidence,
  scope,
  onOpen,
}: {
  evidence: Evidence[];
  confidence: Confidence | null;
  scope: string | null;
  onOpen: (e: Evidence) => void;
}) {
  const { setSelection, setSelectedSymbolId, selection } = useApp();
  const nav = useNavigate();
  if (scope === "general")
    return (
      <div
        className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center"
        data-testid="evidence-general-note"
      >
        <FileSearch className="h-8 w-8 text-slate-600" />
        <p className="text-[13px] text-slate-300">
          General answer - no repository was searched
        </p>
        <p className="max-w-xs text-[12px] text-slate-500">
          This question was answered from general programming knowledge. Ask
          about the loaded repository, or switch scope to "Repository" to force
          a code search.
        </p>
      </div>
    );
  if (!evidence.length)
    return (
      <div
        className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center"
        data-testid="evidence-empty"
      >
        <Crosshair className="h-8 w-8 text-slate-600" />
        <p className="text-[13px] text-slate-300">Evidence appears here</p>
        <p className="max-w-xs text-[12px] text-slate-500">
          Ask a repository question and CodeAtlas retrieves the exact source
          snippets - with file paths and line ranges - that support the answer.
        </p>
      </div>
    );
  return (
    <div
      className="scroll-thin flex-1 space-y-3 overflow-y-auto p-3"
      data-testid="evidence-panel"
    >
      {confidence && <ConfidenceMeter c={confidence} />}
      {evidence.map((e) => {
        const isSel =
          selection?.file_path === e.file_path &&
          selection.start_line === e.start_line &&
          selection.end_line === e.end_line;
        return (
          <div
            key={e.id}
            id={`evidence-${e.id}`}
            data-testid={`evidence-card-${e.id}`}
            className={cn(
              "rounded-lg border bg-panel/40 transition-colors duration-150",
              isSel
                ? "border-violet-500/60"
                : "border-line hover:border-blue-500/50",
            )}
          >
            <div className="flex items-start justify-between gap-2 px-3 pt-2.5">
              <div className="min-w-0">
                <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  Evidence {e.id.replace("E", "")}
                </p>
                <button
                  type="button"
                  data-testid={`evidence-open-${e.id}`}
                  onClick={() => onOpen(e)}
                  className="mt-0.5 flex max-w-full items-center gap-1.5 text-left font-mono text-[12px] text-sky-300 hover:underline"
                  title="Open in source viewer"
                >
                  <span className="truncate">{e.file_path}</span>
                  <span className="shrink-0 text-slate-500">
                    L{e.start_line}-{e.end_line}
                  </span>
                </button>
              </div>
              <div className="flex shrink-0 items-center gap-0.5">
                <CopyButton
                  text={`${e.file_path}:${e.start_line}-${e.end_line}`}
                  label="File path"
                  testId={`evidence-copy-path-${e.id}`}
                />
                <span
                  className="ml-1 rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10.5px] text-slate-300"
                  title="Hybrid relevance score"
                >
                  {Math.round(e.score * 100)}
                </span>
              </div>
            </div>
            <div className="px-3 py-2 text-[12px] leading-snug text-slate-400">
              <span className="text-slate-500">Reason selected: </span>
              {e.ai_note || e.reason}
              {e.ai_note && (
                <p className="mt-1 text-[11px] text-slate-600">
                  Signals: {e.reason}
                </p>
              )}
            </div>
            <CodeBlock
              code={e.code}
              language={e.language}
              startLine={e.start_line}
              className="mx-3 max-h-56 rounded-md"
              testId={`evidence-code-${e.id}`}
            />
            <div className="flex flex-wrap gap-1.5 p-2.5">
              <button
                type="button"
                data-testid={`evidence-select-${e.id}`}
                onClick={() =>
                  setSelection(
                    isSel
                      ? null
                      : {
                          file_path: e.file_path,
                          start_line: e.start_line,
                          end_line: e.end_line,
                          symbol_id: e.symbol_id,
                        },
                  )
                }
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11.5px] transition-colors",
                  isSel
                    ? "border-violet-500/60 bg-violet-500/15 text-violet-200"
                    : "border-line text-slate-400 hover:text-slate-200",
                )}
              >
                <MousePointerSquareDashed className="h-3 w-3" />
                {isSel ? "Selected" : "Select & ask"}
              </button>
              <button
                type="button"
                data-testid={`evidence-source-${e.id}`}
                onClick={() => onOpen(e)}
                className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-[11.5px] text-slate-400 transition-colors hover:text-slate-200"
              >
                <FileSearch className="h-3 w-3" />
                Open file
              </button>
              {e.symbol_id && (
                <button
                  type="button"
                  data-testid={`evidence-explore-${e.id}`}
                  onClick={() => {
                    setSelectedSymbolId(e.symbol_id);
                    nav("/explorer");
                  }}
                  className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-[11.5px] text-slate-400 transition-colors hover:text-slate-200"
                >
                  <Network className="h-3 w-3" />
                  Explore graph
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
