import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import {
  ChevronLeft,
  ChevronRight,
  FileCode2,
  History,
  ListOrdered,
  Loader2,
  MessageSquareCode,
  Network,
  RefreshCw,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { errMsg, useApp } from "@/lib/appState";
import type {
  DescribeOut,
  FileOut,
  SymbolSummary,
  WalkthroughOut,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { CodeBlock, CopyButton, type LineRange } from "@/components/CodeBlock";
import { Markdown } from "@/components/Markdown";
import {
  AlternativesDialog,
  HistoryDialog,
} from "@/components/workspace/ToolDialogs";

const KIND_COLOR: Record<string, string> = {
  function: "text-sky-300",
  method: "text-blue-300",
  class: "text-violet-300",
  interface: "text-violet-300",
  struct: "text-violet-300",
};

export function SourcePanel({
  repoId,
  onAskFile,
}: {
  repoId: string;
  onAskFile: (path: string) => void;
}) {
  const {
    selectedFile,
    focus,
    selection,
    setSelection,
    mode,
    setSelectedSymbolId,
  } = useApp();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [activeSym, setActiveSym] = useState<SymbolSummary | null>(null);
  const [walk, setWalk] = useState<WalkthroughOut | null>(null);
  const [step, setStep] = useState(0);
  const [dialog, setDialog] = useState<"alt" | "hist" | null>(null);
  const [descOpen, setDescOpen] = useState(true);

  const file = useQuery({
    queryKey: ["file", repoId, selectedFile],
    queryFn: () =>
      apiGet<FileOut>(
        `/repos/${repoId}/file?path=${encodeURIComponent(selectedFile!)}`,
      ),
    enabled: !!selectedFile,
  });
  const desc = useQuery({
    queryKey: ["describe", repoId, selectedFile],
    queryFn: () =>
      apiPost<DescribeOut>("/ai/describe-file", {
        repo_id: repoId,
        path: selectedFile,
        mode,
      }),
    enabled: !!selectedFile && !!file.data,
    retry: false,
    staleTime: Infinity,
  });
  const regen = useMutation({
    mutationFn: () =>
      apiPost<DescribeOut>("/ai/describe-file", {
        repo_id: repoId,
        path: selectedFile,
        mode,
        refresh: true,
      }),
    onSuccess: (d) => qc.setQueryData(["describe", repoId, selectedFile], d),
  });
  const walkM = useMutation({
    mutationFn: (s: SymbolSummary) =>
      apiPost<WalkthroughOut>("/ai/walkthrough", {
        repo_id: repoId,
        symbol_id: s.id,
        mode,
      }),
    onSuccess: (w) => {
      setWalk(w);
      setStep(0);
    },
  });

  useEffect(() => {
    setActiveSym(null);
    setWalk(null);
  }, [selectedFile]);
  useEffect(() => {
    if (focus && file.data) {
      const s = file.data.symbols.find(
        (x) => x.start_line === focus.start && x.kind !== "class",
      );
      if (s) setActiveSym(s);
    }
  }, [focus, file.data]);

  const ranges = useMemo<LineRange[]>(() => {
    const r: LineRange[] = [];
    if (activeSym)
      r.push({
        start: activeSym.start_line,
        end: activeSym.end_line,
        tone: "evidence",
      });
    if (focus && focus.path === selectedFile)
      r.push({ start: focus.start, end: focus.end, tone: "evidence" });
    if (selection && selection.file_path === selectedFile)
      r.push({
        start: selection.start_line,
        end: selection.end_line,
        tone: "selection",
      });
    if (walk && walk.steps[step])
      r.push({
        start: walk.steps[step].start_line,
        end: walk.steps[step].end_line,
        tone: "step",
      });
    return r;
  }, [activeSym, focus, selection, walk, step, selectedFile]);

  const scrollTo = useMemo(() => {
    if (walk && walk.steps[step])
      return { line: walk.steps[step].start_line, nonce: step + 1000 };
    if (focus && focus.path === selectedFile)
      return { line: focus.start, nonce: focus.nonce };
    return null;
  }, [walk, step, focus, selectedFile]);

  const onLine = (line: number, shift: boolean) => {
    if (!selectedFile) return;
    if (shift && selection && selection.file_path === selectedFile)
      setSelection({
        file_path: selectedFile,
        start_line: Math.min(selection.start_line, line),
        end_line: Math.max(selection.start_line, line),
      });
    else
      setSelection({
        file_path: selectedFile,
        start_line: line,
        end_line: line,
      });
  };

  if (!selectedFile)
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
        <FileCode2 className="h-8 w-8 text-slate-600" />
        <p className="text-[13px] text-slate-300">No file open</p>
        <p className="max-w-xs text-[12px] text-slate-500">
          Pick a file from the explorer, or click an evidence snippet to jump to
          its exact lines.
        </p>
      </div>
    );

  const symbols = file.data?.symbols ?? [];
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-line px-3 py-2">
        <p
          data-testid="source-file-path"
          className="min-w-0 flex-1 truncate font-mono text-[12px] text-slate-300"
        >
          {selectedFile.split("/").map((p, i, a) => (
            <span key={i}>
              {p}
              {i < a.length - 1 && (
                <span className="mx-1 text-slate-600">/</span>
              )}
            </span>
          ))}
        </p>
        <CopyButton
          text={selectedFile}
          label="File path"
          testId="source-copy-path"
        />
        <button
          type="button"
          data-testid="ask-about-file-button"
          onClick={() => onAskFile(selectedFile)}
          className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-[11.5px] text-slate-400 transition-colors hover:text-slate-200"
        >
          <MessageSquareCode className="h-3 w-3" /> Ask about file
        </button>
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <div
          className="border-b border-line bg-panel/40 px-3 py-2.5"
          data-testid="file-description"
        >
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setDescOpen((o) => !o)}
              className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-violet-300"
            >
              <Sparkles className="h-3.5 w-3.5" /> AI file summary{" "}
              <ChevronRight
                className={cn(
                  "h-3 w-3 transition-transform",
                  descOpen && "rotate-90",
                )}
              />
            </button>
            {desc.data && (
              <button
                type="button"
                data-testid="regenerate-description"
                title="Regenerate in current mode"
                onClick={() => regen.mutate()}
                className="ml-auto text-slate-500 hover:text-slate-200"
              >
                {regen.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" />
                )}
              </button>
            )}
          </div>
          {descOpen && (
            <div className="mt-1.5 text-[12.5px]">
              {desc.isLoading && (
                <div className="space-y-1.5">
                  <div className="skeleton h-3 w-11/12" />
                  <div className="skeleton h-3 w-4/5" />
                  <div className="skeleton h-3 w-2/3" />
                </div>
              )}
              {desc.isError && (
                <p className="text-[12px] text-red-400">{errMsg(desc.error)}</p>
              )}
              {desc.data && <Markdown text={desc.data.description} />}
            </div>
          )}
        </div>
        {symbols.length > 0 && (
          <div
            className="flex flex-wrap gap-1 border-b border-line px-3 py-2"
            data-testid="file-symbols"
          >
            {symbols.map((s) => (
              <button
                key={s.id}
                type="button"
                data-testid={`symbol-chip-${s.name}`}
                onClick={() => {
                  setActiveSym(activeSym?.id === s.id ? null : s);
                  setWalk(null);
                }}
                className={cn(
                  "rounded-md border px-1.5 py-0.5 font-mono text-[11.5px] transition-colors",
                  activeSym?.id === s.id
                    ? "border-blue-500/60 bg-blue-500/15 text-sky-200"
                    : "border-line text-slate-400 hover:text-slate-200",
                )}
              >
                <span
                  className={cn(
                    "mr-1 text-[10px] uppercase",
                    KIND_COLOR[s.kind],
                  )}
                >
                  {s.kind.slice(0, 2)}
                </span>
                {s.name}
              </button>
            ))}
          </div>
        )}
        <AnimatePresence>
          {activeSym && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden border-b border-line bg-blue-500/[0.04]"
            >
              <div
                className="flex flex-wrap items-center gap-1.5 px-3 py-2"
                data-testid="symbol-actions"
              >
                <span className="mr-1 font-mono text-[12px] text-sky-200">
                  {activeSym.name}(){" "}
                  <span className="text-slate-500">
                    L{activeSym.start_line}-{activeSym.end_line}
                  </span>
                </span>
                {activeSym.kind !== "class" && (
                  <ActBtn
                    testId="walkthrough-button"
                    icon={walkM.isPending ? Loader2 : ListOrdered}
                    spin={walkM.isPending}
                    onClick={() => walkM.mutate(activeSym)}
                  >
                    Step-by-step
                  </ActBtn>
                )}
                <ActBtn
                  testId="select-symbol-button"
                  icon={MessageSquareCode}
                  onClick={() =>
                    setSelection({
                      file_path: activeSym.file_path,
                      start_line: activeSym.start_line,
                      end_line: activeSym.end_line,
                      symbol_id: activeSym.id,
                    })
                  }
                >
                  Ask about it
                </ActBtn>
                <ActBtn
                  testId="alternatives-button"
                  icon={Wand2}
                  onClick={() => setDialog("alt")}
                >
                  Alternatives
                </ActBtn>
                <ActBtn
                  testId="history-button"
                  icon={History}
                  onClick={() => setDialog("hist")}
                >
                  History
                </ActBtn>
                <ActBtn
                  testId="open-in-explorer-button"
                  icon={Network}
                  onClick={() => {
                    setSelectedSymbolId(activeSym.id);
                    nav("/explorer");
                  }}
                >
                  Code Explorer
                </ActBtn>
              </div>
              {walkM.isError && (
                <p className="px-3 pb-2 text-[12px] text-red-400">
                  {errMsg(walkM.error)}
                </p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
        {walk && (
          <div
            className="sticky top-0 z-20 border-b border-sky-500/30 bg-[#0b1626]/95 px-3 py-2.5 backdrop-blur"
            data-testid="walkthrough-panel"
          >
            <div className="flex items-center gap-2">
              <p className="text-[11px] font-medium uppercase tracking-wider text-sky-300">
                Walkthrough · {walk.symbol.name}()
              </p>
              <span className="font-mono text-[11px] text-slate-500">
                step {step + 1}/{walk.steps.length}
              </span>
              <div className="ml-auto flex items-center gap-1">
                <button
                  type="button"
                  data-testid="walkthrough-prev"
                  disabled={step === 0}
                  onClick={() => setStep((s) => s - 1)}
                  className="rounded p-1 text-slate-400 hover:bg-slate-800 disabled:opacity-30"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  data-testid="walkthrough-next"
                  disabled={step >= walk.steps.length - 1}
                  onClick={() => setStep((s) => s + 1)}
                  className="rounded p-1 text-slate-400 hover:bg-slate-800 disabled:opacity-30"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  data-testid="walkthrough-close"
                  onClick={() => setWalk(null)}
                  className="rounded p-1 text-slate-500 hover:bg-slate-800"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            {step === 0 && (
              <div className="mt-1.5 space-y-1 text-[12px] text-slate-400">
                <p>
                  <span className="text-slate-500">Purpose: </span>
                  {walk.purpose}
                </p>
                {walk.parameters.length > 0 && (
                  <p>
                    <span className="text-slate-500">Parameters: </span>
                    {walk.parameters.map((p) => (
                      <span key={p.name} className="mr-2">
                        <code className="text-sky-300">{p.name}</code> -{" "}
                        {p.description}
                      </span>
                    ))}
                  </p>
                )}
                {walk.variables.length > 0 && (
                  <p>
                    <span className="text-slate-500">Key variables: </span>
                    {walk.variables.map((p) => (
                      <span key={p.name} className="mr-2">
                        <code className="text-sky-300">{p.name}</code> -{" "}
                        {p.description}
                      </span>
                    ))}
                  </p>
                )}
                <p>
                  <span className="text-slate-500">Returns: </span>
                  {walk.returns}
                </p>
              </div>
            )}
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 6 }}
              animate={{ opacity: 1, x: 0 }}
              className="mt-2 rounded-md border border-line bg-editor/70 p-2"
            >
              <p className="text-[13px] font-medium text-slate-100">
                <span className="mr-1.5 rounded bg-sky-500/15 px-1.5 py-0.5 text-[10px] uppercase text-sky-300">
                  {walk.steps[step].kind}
                </span>
                {walk.steps[step].title}{" "}
                <span className="font-mono text-[11px] text-slate-500">
                  L{walk.steps[step].start_line}-{walk.steps[step].end_line}
                </span>
              </p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-slate-400">
                {walk.steps[step].explanation}
              </p>
            </motion.div>
          </div>
        )}
        {selection && selection.file_path === selectedFile && (
          <p
            className="px-3 pt-2 text-[11.5px] text-violet-300"
            data-testid="selection-hint"
          >
            Lines {selection.start_line}-{selection.end_line} selected ·
            shift-click a line to extend · ask in the chat
          </p>
        )}
        {file.isLoading && (
          <div className="space-y-1.5 p-3">
            {Array.from({ length: 14 }).map((_, i) => (
              <div
                key={i}
                className="skeleton h-3.5"
                style={{ width: `${30 + ((i * 23) % 60)}%` }}
              />
            ))}
          </div>
        )}
        {file.isError && (
          <p className="p-3 text-[12px] text-red-400">{errMsg(file.error)}</p>
        )}
        {file.data && (
          <CodeBlock
            code={file.data.content}
            language={file.data.language}
            ranges={ranges}
            scrollTo={scrollTo}
            onLineClick={onLine}
            className="m-2 rounded-md"
            testId="source-code"
          />
        )}
      </div>
      <AlternativesDialog
        repoId={repoId}
        symbol={activeSym}
        open={dialog === "alt"}
        onOpenChange={(o) => setDialog(o ? "alt" : null)}
      />
      <HistoryDialog
        repoId={repoId}
        symbol={activeSym}
        open={dialog === "hist"}
        onOpenChange={(o) => setDialog(o ? "hist" : null)}
      />
    </div>
  );
}

function ActBtn({
  children,
  icon: Icon,
  onClick,
  testId,
  spin,
}: {
  children: React.ReactNode;
  icon: typeof X;
  onClick: () => void;
  testId: string;
  spin?: boolean;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className="inline-flex items-center gap-1 rounded-md border border-line bg-panel/60 px-2 py-1 text-[11.5px] text-slate-300 transition-colors hover:border-blue-500/50 hover:text-white"
    >
      <Icon className={cn("h-3 w-3", spin && "animate-spin")} />
      {children}
    </button>
  );
}
