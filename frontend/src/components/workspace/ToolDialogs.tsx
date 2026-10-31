import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  GitCommitHorizontal,
  Loader2,
  Sparkles,
} from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { errMsg, useApp } from "@/lib/appState";
import type {
  AlternativesOut,
  HistoryExplainOut,
  HistoryOut,
  SymbolSummary,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/CodeBlock";
import { Markdown } from "@/components/Markdown";

interface Props {
  repoId: string | null;
  symbol: SymbolSummary | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}

export function AlternativesDialog({
  repoId,
  symbol,
  open,
  onOpenChange,
  concept,
}: Props & { concept?: string }) {
  const { mode } = useApp();
  const gen = useMutation({
    mutationFn: () =>
      apiPost<AlternativesOut>(
        "/ai/alternatives",
        symbol
          ? { repo_id: repoId, symbol_id: symbol.id, mode }
          : { concept, mode },
      ),
  });
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) gen.reset();
      }}
    >
      <DialogContent
        className="max-h-[88vh] max-w-4xl overflow-y-auto scroll-thin"
        data-testid="alternatives-dialog"
      >
        <DialogHeader>
          <DialogTitle>
            Alternative implementations {symbol ? `of ${symbol.name}()` : ""}
          </DialogTitle>
          <DialogDescription>
            Compare different ways to implement the same behaviour.
          </DialogDescription>
        </DialogHeader>
        {!gen.data && (
          <Button
            data-testid="alternatives-generate-button"
            disabled={gen.isPending}
            onClick={() => gen.mutate()}
            className="self-start"
          >
            {gen.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}{" "}
            Generate alternatives
          </Button>
        )}
        {gen.isPending && (
          <div className="space-y-2">
            <div className="skeleton h-5 w-1/3" />
            <div className="skeleton h-32" />
            <div className="skeleton h-5 w-1/4" />
            <div className="skeleton h-32" />
          </div>
        )}
        {gen.isError && (
          <p className="text-[13px] text-red-400">{errMsg(gen.error)}</p>
        )}
        {gen.data?.source && (
          <div>
            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-emerald-400">
              Original - from repository · {gen.data.source.file_path} L
              {gen.data.source.start_line}-{gen.data.source.end_line}
            </p>
            <CodeBlock
              code={gen.data.source.code}
              language={gen.data.source.language}
              startLine={gen.data.source.start_line}
              className="max-h-60"
            />
          </div>
        )}
        {gen.data?.alternatives.map((a, i) => (
          <div
            key={i}
            data-testid={`alternative-${i}`}
            className="rounded-lg border border-violet-500/30 bg-violet-500/[0.04] p-3"
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="rounded bg-violet-600/80 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">
                AI generated - not from repo
              </span>
              <p className="text-[14px] font-medium text-slate-100">
                {a.title}
              </p>
            </div>
            <CodeBlock
              code={a.code}
              language={a.language}
              className="max-h-72"
            />
            <div className="mt-2.5 grid gap-3 text-[12.5px] md:grid-cols-2">
              <div>
                <p className="mb-1 font-medium text-slate-300">Differences</p>
                <p className="text-slate-400">{a.differences}</p>
              </div>
              <div>
                <p className="mb-1 font-medium text-slate-300">When to use</p>
                <p className="text-slate-400">{a.when_to_use}</p>
              </div>
              <div>
                <p className="mb-1 font-medium text-emerald-300">Advantages</p>
                <ul className="list-disc space-y-0.5 pl-4 text-slate-400">
                  {a.pros.map((p, k) => (
                    <li key={k}>{p}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="mb-1 font-medium text-orange-300">
                  Disadvantages
                </p>
                <ul className="list-disc space-y-0.5 pl-4 text-slate-400">
                  {a.cons.map((p, k) => (
                    <li key={k}>{p}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ))}
      </DialogContent>
    </Dialog>
  );
}

export function HistoryDialog({ repoId, symbol, open, onOpenChange }: Props) {
  const { mode } = useApp();
  const [idx, setIdx] = useState(0);
  const hist = useQuery({
    queryKey: ["history", repoId, symbol?.id],
    queryFn: () =>
      apiGet<HistoryOut>(`/repos/${repoId}/symbols/${symbol!.id}/history`),
    enabled: open && !!repoId && !!symbol,
  });
  const explain = useMutation({
    mutationFn: () =>
      apiPost<HistoryExplainOut>("/ai/history-explain", {
        repo_id: repoId,
        symbol_id: symbol!.id,
        mode,
      }),
  });
  const c = hist.data?.commits[idx];
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) {
          explain.reset();
          setIdx(0);
        }
      }}
    >
      <DialogContent
        className="max-h-[88vh] max-w-4xl overflow-y-auto scroll-thin"
        data-testid="history-dialog"
      >
        <DialogHeader>
          <DialogTitle>Change history · {symbol?.name}()</DialogTitle>
          <DialogDescription>
            Real commits from Git (git log -L) touching {symbol?.file_path}{" "}
            lines {symbol?.start_line}-{symbol?.end_line}.
          </DialogDescription>
        </DialogHeader>
        {hist.isLoading && (
          <div className="space-y-2">
            <div className="skeleton h-8" />
            <div className="skeleton h-40" />
          </div>
        )}
        {hist.isError && (
          <p className="text-[13px] text-red-400">{errMsg(hist.error)}</p>
        )}
        {hist.data && !hist.data.available && (
          <div
            data-testid="history-unavailable"
            className="flex gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-[13px] text-amber-100"
          >
            <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400" />
            <p>{hist.data.reason}</p>
          </div>
        )}
        {hist.data?.available && (
          <div className="grid gap-3 md:grid-cols-[240px_1fr]">
            <div className="space-y-1">
              {hist.data.commits.map((cm, i) => (
                <button
                  key={cm.hash}
                  type="button"
                  data-testid={`history-commit-${i}`}
                  onClick={() => setIdx(i)}
                  className={cn(
                    "w-full rounded-md border px-2.5 py-2 text-left transition-colors",
                    i === idx
                      ? "border-blue-500/60 bg-blue-500/10"
                      : "border-line hover:border-slate-600",
                  )}
                >
                  <p className="flex items-center gap-1.5 font-mono text-[11.5px] text-sky-300">
                    <GitCommitHorizontal className="h-3.5 w-3.5" />
                    {cm.short}
                    <span className="ml-auto text-emerald-400">
                      +{cm.added}
                    </span>
                    <span className="text-red-400">-{cm.removed}</span>
                  </p>
                  <p className="mt-0.5 truncate text-[12px] text-slate-300">
                    {cm.message}
                  </p>
                  <p className="text-[11px] text-slate-500">
                    {cm.author} · {cm.date.slice(0, 10)}
                  </p>
                </button>
              ))}
            </div>
            {c && (
              <div
                className="min-w-0 overflow-auto rounded-lg border border-line bg-editor font-mono text-[12px] scroll-thin"
                data-testid="history-diff"
              >
                {c.lines.map((l, i) => (
                  <div
                    key={i}
                    className={cn(
                      "whitespace-pre px-3",
                      l.type === "add" && "bg-emerald-900/25 text-emerald-300",
                      l.type === "del" && "bg-red-900/25 text-red-300",
                      l.type === "hunk" && "bg-slate-800/60 text-slate-500",
                      l.type === "ctx" && "text-slate-400",
                    )}
                  >
                    {l.type === "add" ? "+ " : l.type === "del" ? "- " : "  "}
                    {l.text}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {hist.data?.available && (
          <div>
            {!explain.data && (
              <Button
                data-testid="history-explain-button"
                variant="secondary"
                disabled={explain.isPending}
                onClick={() => explain.mutate()}
              >
                {explain.isPending && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                Explain these changes
              </Button>
            )}
            {explain.isError && (
              <p className="text-[13px] text-red-400">
                {errMsg(explain.error)}
              </p>
            )}
            {explain.data && (
              <div className="rounded-lg border border-line bg-panel/50 p-3">
                <Markdown text={explain.data.explanation} />
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
