import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { apiPost } from "@/lib/api";
import { errMsg, useApp } from "@/lib/appState";
import type { CompareOut, SymbolSummary } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/CodeBlock";

export function CompareDialog({
  repoId,
  a,
  b,
  open,
  onOpenChange,
}: {
  repoId: string;
  a?: SymbolSummary;
  b?: SymbolSummary;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const { mode } = useApp();
  const cmp = useMutation({
    mutationFn: () =>
      apiPost<CompareOut>("/ai/compare", {
        repo_id: repoId,
        a: a!.id,
        b: b!.id,
        mode,
      }),
  });
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) cmp.reset();
      }}
    >
      <DialogContent
        className="max-h-[90vh] max-w-5xl overflow-y-auto scroll-thin"
        data-testid="compare-dialog"
      >
        <DialogHeader>
          <DialogTitle>
            Compare {a?.name}() vs {b?.name}()
          </DialogTitle>
          <DialogDescription>
            Side-by-side comparison based on the actual source code and static
            call relationships.
          </DialogDescription>
        </DialogHeader>
        {!cmp.data && !cmp.isPending && (
          <Button
            data-testid="compare-run-button"
            onClick={() => cmp.mutate()}
            className="self-start"
          >
            Run comparison
          </Button>
        )}
        {cmp.isPending && (
          <div className="space-y-2">
            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
            <div className="skeleton h-24" />
            <div className="skeleton h-40" />
          </div>
        )}
        {cmp.isError && (
          <p className="text-[13px] text-red-400">{errMsg(cmp.error)}</p>
        )}
        {cmp.data && (
          <div className="space-y-4 text-[12.5px]">
            <div className="grid gap-3 md:grid-cols-2">
              {[cmp.data.a, cmp.data.b].map((s, i) => (
                <div key={s.id}>
                  <p className="mb-1 font-mono text-[12px]">
                    <span className="mr-1.5 rounded bg-violet-600 px-1.5 text-[10px] font-bold text-white">
                      {i ? "B" : "A"}
                    </span>
                    <span className="text-slate-100">{s.name}()</span>{" "}
                    <span className="text-slate-500">
                      {s.file_path} L{s.start_line}-{s.end_line}
                    </span>
                  </p>
                  <CodeBlock
                    code={s.code}
                    language={s.language}
                    startLine={s.start_line}
                    className="max-h-56"
                  />
                </div>
              ))}
            </div>
            <div
              className="overflow-hidden rounded-lg border border-line"
              data-testid="compare-table"
            >
              <div className="grid grid-cols-[160px_1fr_1fr] bg-panel text-[11px] font-medium uppercase tracking-wider text-slate-500">
                <p className="p-2">Aspect</p>
                <p className="border-l border-line p-2">
                  A · {cmp.data.a.name}
                </p>
                <p className="border-l border-line p-2">
                  B · {cmp.data.b.name}
                </p>
              </div>
              {cmp.data.rows.map((r, i) => (
                <div
                  key={i}
                  className="grid grid-cols-[160px_1fr_1fr] border-t border-line"
                >
                  <p className="p-2 font-medium text-slate-300">{r.aspect}</p>
                  <p className="border-l border-line p-2 text-slate-400">
                    {r.a}
                  </p>
                  <p className="border-l border-line p-2 text-slate-400">
                    {r.b}
                  </p>
                </div>
              ))}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-3">
                <p className="mb-1.5 font-medium text-emerald-300">
                  Similarities
                </p>
                <ul className="list-disc space-y-1 pl-4 text-slate-400">
                  {cmp.data.similarities.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-orange-500/25 bg-orange-500/5 p-3">
                <p className="mb-1.5 font-medium text-orange-300">
                  Differences
                </p>
                <ul className="list-disc space-y-1 pl-4 text-slate-400">
                  {cmp.data.differences.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              </div>
            </div>
            {cmp.data.summary && (
              <p className="rounded-lg border border-line bg-panel/50 p-3 text-slate-300">
                {cmp.data.summary}
              </p>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
