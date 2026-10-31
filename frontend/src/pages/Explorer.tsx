import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import {
  AlertTriangle,
  ChevronsDownUp,
  ChevronsUpDown,
  Code2,
  GitCompareArrows,
  GitFork,
  Home,
  LayoutGrid,
  Loader2,
  Network,
  Search,
  Sparkles,
  Trash2,
  Undo2,
  Workflow,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";
import { errMsg, useApp, useCurrentRepo } from "@/lib/appState";
import type {
  FlowOut,
  GraphEdge,
  GraphOut,
  ImpactExplainOut,
  ImpactOut,
  SearchOut,
  SymbolDetail,
  SymbolSummary,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/CodeBlock";
import { Markdown } from "@/components/Markdown";
import {
  nodeTypes,
  type SymbolNodeData,
} from "@/components/explorer/GraphNodes";
import { CompareDialog } from "@/components/explorer/CompareDialog";
import { useOpenUpload } from "@/components/layout/AppShell";

type ViewMode = "graph" | "flow";

function merge(
  base: GraphOut | undefined,
  extras: GraphOut[],
): { nodes: SymbolSummary[]; edges: GraphEdge[] } {
  const nodes = new Map<string, SymbolSummary>();
  const edges = new Map<string, GraphEdge>();
  for (const g of [base, ...extras]) {
    if (!g) continue;
    g.nodes.forEach((n) => nodes.set(n.id, n));
    g.edges.forEach((e) => edges.set(e.id, e));
  }
  return { nodes: [...nodes.values()], edges: [...edges.values()] };
}

function layered(
  ids: string[],
  levelOf: Map<string, number>,
  dx: number,
  dy: number,
  vertical: boolean,
) {
  const groups = new Map<number, string[]>();
  ids.forEach((id) => {
    const l = levelOf.get(id) ?? 0;
    groups.set(l, [...(groups.get(l) ?? []), id]);
  });
  const pos = new Map<string, { x: number; y: number }>();
  groups.forEach((g, l) =>
    g.forEach((id, i) => {
      const off = i - (g.length - 1) / 2;
      pos.set(
        id,
        vertical ? { x: off * dx, y: l * dy } : { x: l * dx, y: off * dy },
      );
    }),
  );
  return pos;
}

function callLevels(
  nodes: SymbolSummary[],
  edges: GraphEdge[],
  root: string | null,
) {
  const lv = new Map<string, number>();
  const calls = edges.filter((e) => e.kind === "calls");
  const bfs = (starts: string[], dir: 1 | -1) => {
    const q = [...starts];
    while (q.length) {
      const cur = q.shift()!;
      for (const e of calls) {
        const [from, to] =
          dir === 1 ? [e.source, e.target] : [e.target, e.source];
        if (from === cur && !lv.has(to)) {
          lv.set(to, lv.get(cur)! + dir);
          q.push(to);
        }
      }
    }
  };
  if (root && nodes.some((n) => n.id === root)) {
    lv.set(root, 0);
    bfs([root], 1);
    bfs([root], -1);
  } else {
    const targets = new Set(calls.map((e) => e.target));
    const starts = nodes.filter((n) => !targets.has(n.id)).map((n) => n.id);
    starts.forEach((s) => lv.set(s, 0));
    bfs(starts, 1);
  }
  edges
    .filter((e) => e.kind === "contains")
    .forEach((e) => {
      if (!lv.has(e.source)) lv.set(e.source, (lv.get(e.target) ?? 0) - 1);
    });
  return lv;
}

function ExplorerInner() {
  const {
    repoId,
    selectedSymbolId,
    setSelectedSymbolId,
    openFile,
    setSelection,
  } = useApp();
  const { data: repo } = useCurrentRepo();
  const ready = repo?.status === "ready";
  const nav = useNavigate();
  const openUpload = useOpenUpload();
  const rf = useReactFlow();
  const [view, setView] = useState<ViewMode>("graph");
  const [extras, setExtras] = useState<GraphOut[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(selectedSymbolId);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [removed, setRemoved] = useState<string[]>([]);
  const [compare, setCompare] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [layoutNonce, setLayoutNonce] = useState(0);
  const [q, setQ] = useState("");
  const [flowActive, setFlowActive] = useState<string | null>(null);
  const [showCons, setShowCons] = useState(true);

  const root = selectedSymbolId;
  const graph = useQuery({
    queryKey: ["graph", repoId, root],
    queryFn: () =>
      apiGet<GraphOut>(
        `/repos/${repoId}/graph${root ? `?symbol_id=${root}&depth=2` : ""}`,
      ),
    enabled: ready,
  });
  const detail = useQuery({
    queryKey: ["symbol", repoId, selectedId],
    queryFn: () =>
      apiGet<SymbolDetail>(`/repos/${repoId}/symbols/${selectedId}`),
    enabled: ready && !!selectedId,
  });
  const flowTarget = selectedId ?? root;
  const flow = useQuery({
    queryKey: ["flow", repoId, flowTarget],
    queryFn: () =>
      apiGet<FlowOut>(`/repos/${repoId}/symbols/${flowTarget}/flow`),
    enabled: ready && view === "flow" && !!flowTarget,
    retry: false,
  });
  const nameSearch = useQuery({
    queryKey: ["symsearch", repoId, q],
    queryFn: () =>
      apiGet<SymbolSummary[]>(
        `/repos/${repoId}/symbols?q=${encodeURIComponent(q)}`,
      ),
    enabled: ready && q.length >= 2,
  });
  const hybrid = useQuery({
    queryKey: ["hybrid", repoId, q],
    queryFn: () =>
      apiGet<SearchOut>(`/repos/${repoId}/search?q=${encodeURIComponent(q)}`),
    enabled: ready && q.length >= 3,
  });
  const impact = useMutation({
    mutationFn: (ids: string[]) =>
      apiPost<ImpactOut>(`/repos/${repoId}/impact`, { removed: ids }),
    onError: (e) => toast.error(errMsg(e)),
  });
  const explain = useMutation({
    mutationFn: (ids: string[]) =>
      apiPost<ImpactExplainOut>(`/repos/${repoId}/impact/explain`, {
        removed: ids,
      }),
  });

  useEffect(() => {
    setExtras([]);
    setCollapsed(new Set());
    setRemoved([]);
    impact.reset();
    explain.reset();
    setSelectedId(root);
  }, [root, repoId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (removed.length) impact.mutate(removed);
    else impact.reset();
    explain.reset();
  }, [removed]); // eslint-disable-line react-hooks/exhaustive-deps

  const data = useMemo(() => merge(graph.data, extras), [graph.data, extras]);
  const hidden = useMemo(() => {
    const h = new Set<string>();
    const stack = [...collapsed];
    while (stack.length) {
      const cur = stack.pop()!;
      data.edges
        .filter((e) => e.source === cur && e.kind === "calls")
        .forEach((e) => {
          if (
            !h.has(e.target) &&
            e.target !== root &&
            !collapsed.has(e.target)
          ) {
            h.add(e.target);
            stack.push(e.target);
          }
        });
    }
    return h;
  }, [collapsed, data.edges, root]);

  const imp = impact.data;
  const affected = useMemo(() => {
    const m = new Map<string, "direct" | "transitive" | "orphaned">();
    imp?.transitive_dependents.forEach((s) => m.set(s.id, "transitive"));
    imp?.orphaned.forEach((s) => m.set(s.id, "orphaned"));
    imp?.direct_dependents.forEach((s) => m.set(s.id, "direct"));
    return m;
  }, [imp]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    if (view !== "graph") return;
    const visible = data.nodes.filter((n) => !hidden.has(n.id));
    const pos = layered(
      visible.map((n) => n.id),
      callLevels(visible, data.edges, root),
      300,
      100,
      false,
    );
    setNodes((prev) => {
      const old = new Map(prev.map((p) => [p.id, p.position]));
      return visible.map((n) => {
        const d: SymbolNodeData = {
          sym: n,
          root: n.id === root,
          selected: n.id === selectedId,
          removed: removed.includes(n.id),
          affected: affected.get(n.id),
          compareIndex: compare.indexOf(n.id) + 1 || undefined,
          collapsedCount: collapsed.has(n.id)
            ? data.edges.filter(
                (e) => e.source === n.id && hidden.has(e.target),
              ).length
            : undefined,
        };
        return {
          id: n.id,
          type: "symbol",
          position: (layoutNonce === 0 && old.get(n.id)) ||
            pos.get(n.id) || { x: 0, y: 0 },
          data: d,
        };
      });
    });
    setEdges(
      data.edges
        .filter((e) => !hidden.has(e.source) && !hidden.has(e.target))
        .map((e) => {
          const broken =
            removed.includes(e.source) || removed.includes(e.target);
          return {
            id: e.id,
            source: e.source,
            target: e.target,
            type: "smoothstep",
            animated: broken || e.source === root,
            label: broken
              ? "broken"
              : e.kind === "contains"
                ? "contains"
                : undefined,
            labelStyle: { fill: broken ? "#F87171" : "#A78BFA", fontSize: 10 },
            labelBgStyle: { fill: "#0B0F17" },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: broken
                ? "#EF4444"
                : e.kind === "contains"
                  ? "#8B5CF6"
                  : "#475569",
            },
            style: {
              stroke: broken
                ? "#EF4444"
                : e.kind === "contains"
                  ? "#8B5CF6"
                  : "#475569",
              strokeDasharray:
                broken || e.kind === "contains" ? "5 4" : undefined,
              strokeWidth: 1.4,
            },
          };
        }),
    );
  }, [
    view,
    data,
    hidden,
    root,
    selectedId,
    removed,
    affected,
    compare,
    collapsed,
    layoutNonce,
    setNodes,
    setEdges,
  ]);

  useEffect(() => {
    if (view !== "flow" || !flow.data) return;
    const lv = new Map<string, number>();
    const start = flow.data.nodes.find((n) => n.kind === "start");
    if (start) {
      lv.set(start.id, 0);
      const qq = [start.id];
      while (qq.length) {
        const cur = qq.shift()!;
        flow.data.edges
          .filter((e) => e.source === cur)
          .forEach((e) => {
            if (!lv.has(e.target)) {
              lv.set(e.target, lv.get(cur)! + 1);
              qq.push(e.target);
            }
          });
      }
    }
    const end = flow.data.nodes.find((n) => n.kind === "end");
    if (end) lv.set(end.id, Math.max(0, ...lv.values()) + 1);
    const pos = layered(
      flow.data.nodes.map((n) => n.id),
      lv,
      280,
      110,
      true,
    );
    setNodes(
      flow.data.nodes.map((n) => ({
        id: n.id,
        type: "flow",
        position: pos.get(n.id) ?? { x: 0, y: 0 },
        data: { node: n, active: n.id === flowActive },
      })),
    );
    setEdges(
      flow.data.edges.map((e) => {
        const back =
          (lv.get(e.target) ?? 0) <= (lv.get(e.source) ?? 0) &&
          e.label === "next";
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          type: "smoothstep",
          label: e.label || undefined,
          animated: back,
          labelStyle: {
            fill:
              e.label === "true"
                ? "#34D399"
                : e.label === "false"
                  ? "#F87171"
                  : "#CBD5E1",
            fontSize: 10,
          },
          labelBgStyle: { fill: "#0B0F17" },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#64748B" },
          style: { stroke: back ? "#8B5CF6" : "#64748B", strokeWidth: 1.4 },
        };
      }),
    );
  }, [view, flow.data, flowActive, setNodes, setEdges, layoutNonce]);

  useEffect(() => {
    const t = setTimeout(() => rf.fitView({ padding: 0.2, duration: 300 }), 60);
    return () => clearTimeout(t);
  }, [graph.data, flow.data, view, layoutNonce, rf]);

  const expand = useMutation({
    mutationFn: (id: string) =>
      apiGet<GraphOut>(`/repos/${repoId}/graph?symbol_id=${id}&depth=1`),
    onSuccess: (g, id) => {
      setExtras((x) => [...x, g]);
      setCollapsed((c) => {
        const n = new Set(c);
        n.delete(id);
        return n;
      });
      toast.success(`Expanded ${g.nodes.length} related symbols`);
    },
  });
  const toggleCompare = (id: string) =>
    setCompare((c) =>
      c.includes(id) ? c.filter((x) => x !== id) : [...c.slice(-1), id],
    );
  const nodeById = (id: string) => data.nodes.find((n) => n.id === id);
  const flowNode = flow.data?.nodes.find((n) => n.id === flowActive);

  if (!repo || !ready)
    return (
      <div
        className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center"
        data-testid="explorer-empty"
      >
        <Network className="h-10 w-10 text-slate-600" />
        <p className="text-[15px] font-medium text-slate-200">
          {repo ? "Repository is still indexing..." : "No repository loaded"}
        </p>
        <p className="max-w-sm text-[13px] text-slate-500">
          Code Explorer turns the functions, classes and call relationships
          extracted with tree-sitter into an interactive graph.
        </p>
        {!repo && (
          <Button onClick={openUpload} data-testid="explorer-upload-button">
            Upload a repository
          </Button>
        )}
      </div>
    );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
        <div className="mr-2 min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Code Explorer
          </p>
          <p className="truncate text-[14px] font-medium text-slate-100">
            {root && nodeById(root)
              ? `${nodeById(root)!.name}() · ${repo.name}`
              : `${repo.name} · overview of most-connected symbols`}
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <input
            data-testid="explorer-search-input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search symbols or code (hybrid search)"
            className="h-8 w-full rounded-md border border-line bg-editor pl-8 pr-7 text-[12.5px] outline-none focus:border-blue-500/60"
          />
          {q && (
            <button
              type="button"
              onClick={() => setQ("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          {q.length >= 2 && (
            <div
              className="absolute left-0 right-0 top-9 z-50 max-h-80 overflow-y-auto rounded-lg border border-line bg-panel p-1 shadow-2xl scroll-thin"
              data-testid="explorer-search-results"
            >
              {(nameSearch.data ?? []).slice(0, 8).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  data-testid={`search-result-${s.name}`}
                  onClick={() => {
                    setSelectedSymbolId(s.id);
                    setQ("");
                    setView("graph");
                  }}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[12px] hover:bg-slate-800"
                >
                  <span className="text-[10px] uppercase text-sky-400">
                    {s.kind.slice(0, 2)}
                  </span>
                  <span className="font-mono text-slate-200">{s.name}</span>
                  <span className="ml-auto truncate text-[10.5px] text-slate-500">
                    {s.file_path}
                  </span>
                </button>
              ))}
              {(hybrid.data?.hits ?? []).filter((h) => h.symbol_id).length >
                0 && (
                <p className="px-2 pb-1 pt-2 text-[10px] uppercase tracking-wider text-slate-500">
                  Related code (hybrid search)
                </p>
              )}
              {(hybrid.data?.hits ?? [])
                .filter((h) => h.symbol_id)
                .slice(0, 5)
                .map((h) => (
                  <button
                    key={h.id}
                    type="button"
                    onClick={() => {
                      setSelectedSymbolId(h.symbol_id);
                      setQ("");
                      setView("graph");
                    }}
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[12px] hover:bg-slate-800"
                  >
                    <span className="font-mono text-slate-300">
                      {h.symbol_name}
                    </span>
                    <span className="ml-auto truncate text-[10.5px] text-slate-500">
                      {h.file_path}:{h.start_line}
                    </span>
                  </button>
                ))}
              {nameSearch.data?.length === 0 && !hybrid.data?.hits.length && (
                <p className="p-2 text-[12px] text-slate-500">No matches</p>
              )}
            </div>
          )}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <div className="inline-flex rounded-lg border border-line bg-editor p-0.5">
            {(
              [
                ["graph", "Call graph", GitFork],
                ["flow", "Execution flow", Workflow],
              ] as const
            ).map(([v, l, I]) => (
              <button
                key={v}
                type="button"
                data-testid={`view-mode-${v}`}
                onClick={() => {
                  if (v === "flow" && !flowTarget) {
                    toast.info("Select a function node first");
                    return;
                  }
                  setView(v);
                }}
                className={cn(
                  "relative flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12.5px] transition-colors",
                  view === v
                    ? "text-sky-300"
                    : "text-slate-500 hover:text-slate-300",
                )}
              >
                {view === v && (
                  <motion.span
                    layoutId="view-pill"
                    className="absolute inset-0 rounded-md bg-slate-800"
                  />
                )}
                <I className="relative h-3.5 w-3.5" />
                <span className="relative">{l}</span>
              </button>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            data-testid="reset-layout-button"
            title="Re-run automatic layout"
            onClick={() => setLayoutNonce((n) => n + 1)}
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            Reset layout
          </Button>
          <Button
            variant="outline"
            size="sm"
            data-testid="original-graph-button"
            title="Discard expansions, collapses and simulations"
            onClick={() => {
              setExtras([]);
              setCollapsed(new Set());
              setRemoved([]);
              setCompare([]);
              setLayoutNonce((n) => n + 1);
            }}
          >
            <Home className="h-3.5 w-3.5" />
            Original
          </Button>
          {root && (
            <Button
              variant="ghost"
              size="sm"
              data-testid="overview-button"
              onClick={() => setSelectedSymbolId(null)}
            >
              Overview
            </Button>
          )}
          <Button
            size="sm"
            data-testid="compare-button"
            disabled={compare.length !== 2}
            onClick={() => setCompareOpen(true)}
            title="Shift-click two nodes or use 'Add to compare'"
          >
            <GitCompareArrows className="h-3.5 w-3.5" />
            Compare {compare.length}/2
          </Button>
        </div>
      </header>

      <AnimatePresence>
        {removed.length > 0 && view === "graph" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden border-b border-orange-500/60 bg-[#3a1607]"
            data-testid="impact-banner"
          >
            <div className="flex flex-wrap items-center gap-2 px-4 py-2 text-[12.5px] text-amber-100">
              <AlertTriangle className="h-4 w-4 text-orange-400" />
              <b>Impact simulation active</b>
              <span className="text-amber-200/80">
                - visualisation only; your repository is not modified.
              </span>
              {impact.isPending && (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              )}
              {imp && (
                <span data-testid="impact-summary">
                  {imp.direct_dependents.length} direct ·{" "}
                  {imp.transitive_dependents.length} indirect dependents ·{" "}
                  {imp.broken_edges.length} broken connections ·{" "}
                  {imp.related_tests.length} tests
                </span>
              )}
              <div className="ml-auto flex gap-1.5">
                <button
                  type="button"
                  onClick={() => setShowCons((s) => !s)}
                  className="rounded border border-orange-500/40 px-2 py-0.5 text-[11.5px] hover:bg-orange-500/10"
                >
                  {showCons ? "Hide" : "Details"}
                </button>
                <button
                  type="button"
                  data-testid="impact-explain-button"
                  disabled={explain.isPending}
                  onClick={() => explain.mutate(removed)}
                  className="inline-flex items-center gap-1 rounded border border-orange-500/40 px-2 py-0.5 text-[11.5px] hover:bg-orange-500/10"
                >
                  {explain.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Sparkles className="h-3 w-3" />
                  )}
                  Explain
                </button>
                <button
                  type="button"
                  data-testid="impact-undo-button"
                  onClick={() => setRemoved((r) => r.slice(0, -1))}
                  className="inline-flex items-center gap-1 rounded bg-orange-700 px-2 py-0.5 text-[11.5px] text-white hover:bg-orange-600"
                >
                  <Undo2 className="h-3 w-3" />
                  Undo
                </button>
                <button
                  type="button"
                  data-testid="impact-reset-button"
                  onClick={() => setRemoved([])}
                  className="rounded bg-orange-700 px-2 py-0.5 text-[11.5px] text-white hover:bg-orange-600"
                >
                  Reset
                </button>
              </div>
            </div>
            {showCons && imp && (
              <div className="grid gap-3 px-4 pb-3 text-[12px] text-amber-100/90 md:grid-cols-2">
                <ul
                  className="list-disc space-y-0.5 pl-4"
                  data-testid="impact-consequences"
                >
                  {imp.consequences.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
                <div className="space-y-1">
                  {imp.related_tests.length > 0 && (
                    <p>
                      <span className="text-amber-300">Related tests: </span>
                      {imp.related_tests
                        .map(
                          (t) => `${t.name} (${t.file_path}:${t.start_line})`,
                        )
                        .join(", ")}
                    </p>
                  )}
                  <p className="text-amber-200/60">{imp.caveat}</p>
                  {explain.data && (
                    <div className="rounded border border-orange-500/30 bg-black/20 p-2">
                      <Markdown text={explain.data.explanation} />
                    </div>
                  )}
                  {explain.isError && (
                    <p className="text-red-300">{errMsg(explain.error)}</p>
                  )}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex min-h-0 flex-1">
        <div
          className="relative min-w-0 flex-1 bg-editor"
          data-testid="graph-canvas"
        >
          {(graph.isLoading || (view === "flow" && flow.isLoading)) && (
            <div className="absolute inset-0 z-10 flex items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-slate-500" />
            </div>
          )}
          {view === "flow" && flow.isError && (
            <div className="absolute inset-x-0 top-6 z-10 mx-auto w-fit rounded-md border border-line bg-panel px-3 py-2 text-[12.5px] text-amber-300">
              {errMsg(flow.error)}
            </div>
          )}
          {view === "graph" && graph.data && graph.data.nodes.length === 0 && (
            <div className="absolute inset-x-0 top-10 z-10 mx-auto w-fit text-[13px] text-slate-500">
              No call relationships were found for this selection.
            </div>
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            minZoom={0.15}
            maxZoom={2}
            onNodeClick={(e, n) => {
              if (view === "flow") {
                setFlowActive(n.id);
                return;
              }
              if (e.shiftKey || e.metaKey) toggleCompare(n.id);
              else setSelectedId(n.id);
            }}
            onPaneClick={() => setFlowActive(null)}
            proOptions={{ hideAttribution: true }}
            colorMode="dark"
          >
            <Background color="#1E293B" gap={22} />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              nodeColor={(n) => (n.type === "flow" ? "#334155" : "#1D4ED8")}
              maskColor="rgba(7,11,18,0.7)"
            />
          </ReactFlow>
          <div className="pointer-events-none absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-3 rounded-full border border-line bg-page/90 px-3 py-1 text-[10.5px] text-slate-500 backdrop-blur">
            {view === "graph" ? (
              <>
                <span>
                  <i className="mr-1 inline-block h-2 w-2 rounded-full bg-sky-400" />
                  function
                </span>
                <span>
                  <i className="mr-1 inline-block h-2 w-2 rounded-full bg-violet-400" />
                  class
                </span>
                <span>
                  <i className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-400" />
                  test
                </span>
                <span>drag · scroll to zoom · shift-click to compare</span>
              </>
            ) : (
              <>
                <span className="text-amber-300">◆ condition</span>
                <span className="text-violet-300">↻ loop</span>
                <span className="text-blue-300">ƒ call</span>
                <span className="text-red-300">↵ return</span>
              </>
            )}
          </div>
        </div>

        <aside
          className="scroll-thin hidden w-[360px] shrink-0 overflow-y-auto border-l border-line bg-evidence md:block"
          data-testid="node-details-panel"
        >
          {view === "flow" ? (
            <div className="space-y-3 p-4">
              <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                Execution flowchart
              </p>
              {flow.data && (
                <p className="font-mono text-[13px] text-slate-100">
                  {flow.data.symbol.name}(){" "}
                  <span className="text-slate-500">
                    {flow.data.symbol.file_path} L{flow.data.symbol.start_line}-
                    {flow.data.symbol.end_line}
                  </span>
                </p>
              )}
              <p className="text-[12px] text-slate-500">
                Generated from the tree-sitter syntax tree of this function:
                conditions, loops, calls and returns in source order. Click a
                node to see its code.
              </p>
              {flowNode && detail.data && (
                <div data-testid="flow-node-detail">
                  <p className="mb-1 text-[12px] text-sky-300">
                    {flowNode.kind} · lines {flowNode.start_line}-
                    {flowNode.end_line}
                  </p>
                  <CodeBlock
                    code={detail.data.code
                      .split("\n")
                      .slice(
                        flowNode.start_line - detail.data.start_line,
                        flowNode.end_line - detail.data.start_line + 1,
                      )
                      .join("\n")}
                    language={detail.data.language}
                    startLine={flowNode.start_line}
                    className="max-h-60"
                  />
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setView("graph")}
              >
                <GitFork className="h-3.5 w-3.5" />
                Back to call graph
              </Button>
            </div>
          ) : !selectedId ? (
            <div className="p-6 text-center text-[12.5px] text-slate-500">
              Click a node to inspect it. Search above to centre the graph on
              any function, or open one from the AI Workspace.
            </div>
          ) : detail.isLoading ? (
            <div className="space-y-2 p-4">
              <div className="skeleton h-5 w-1/2" />
              <div className="skeleton h-3 w-3/4" />
              <div className="skeleton h-28" />
            </div>
          ) : detail.data ? (
            <NodeDetails
              d={detail.data}
              collapsed={collapsed.has(detail.data.id)}
              inCompare={compare.includes(detail.data.id)}
              removed={removed.includes(detail.data.id)}
              expanding={expand.isPending}
              onExpand={() => expand.mutate(detail.data!.id)}
              onCollapse={() =>
                setCollapsed((c) => {
                  const n = new Set(c);
                  if (n.has(detail.data!.id)) n.delete(detail.data!.id);
                  else n.add(detail.data!.id);
                  return n;
                })
              }
              onCompare={() => toggleCompare(detail.data!.id)}
              onRemove={() =>
                setRemoved((r) =>
                  r.includes(detail.data!.id) ? r : [...r, detail.data!.id],
                )
              }
              onFlow={() => setView("flow")}
              onCenter={() => setSelectedSymbolId(detail.data!.id)}
              onPick={(id) => setSelectedId(id)}
              onWorkspace={() => {
                const d = detail.data!;
                setSelectedSymbolId(d.id);
                openFile(d.file_path, d.start_line, d.end_line);
                setSelection({
                  file_path: d.file_path,
                  start_line: d.start_line,
                  end_line: d.end_line,
                  symbol_id: d.id,
                });
                nav("/");
              }}
            />
          ) : null}
        </aside>
      </div>
      <CompareDialog
        repoId={repo.id}
        a={nodeById(compare[0])}
        b={nodeById(compare[1])}
        open={compareOpen}
        onOpenChange={setCompareOpen}
      />
    </div>
  );
}

interface DetailsProps {
  d: SymbolDetail;
  collapsed: boolean;
  inCompare: boolean;
  removed: boolean;
  expanding: boolean;
  onExpand: () => void;
  onCollapse: () => void;
  onCompare: () => void;
  onRemove: () => void;
  onFlow: () => void;
  onCenter: () => void;
  onWorkspace: () => void;
  onPick: (id: string) => void;
}

function NodeDetails({
  d,
  collapsed,
  inCompare,
  removed,
  expanding,
  onExpand,
  onCollapse,
  onCompare,
  onRemove,
  onFlow,
  onCenter,
  onWorkspace,
  onPick,
}: DetailsProps) {
  const isFn = d.kind === "function" || d.kind === "method";
  const list = (title: string, items: SymbolSummary[], testId: string) => (
    <div data-testid={testId}>
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-slate-500">
        {title} ({items.length})
      </p>
      {items.length === 0 ? (
        <p className="text-[12px] text-slate-600">None found statically</p>
      ) : (
        <div className="flex flex-wrap gap-1">
          {items.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onPick(s.id)}
              className="rounded border border-line px-1.5 py-0.5 font-mono text-[11.5px] text-slate-300 hover:border-blue-500/50"
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
  return (
    <div className="space-y-4 p-4 animate-fade-up" data-testid="node-details">
      <div>
        <span className="rounded bg-sky-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-sky-300">
          {d.kind}
        </span>
        <p
          data-testid="node-details-name"
          className="mt-1.5 font-mono text-[15px] text-slate-100"
        >
          {d.parent && d.kind === "method" ? `${d.parent}.` : ""}
          {d.name}()
        </p>
        <p
          className="font-mono text-[11.5px] text-slate-500"
          data-testid="node-details-location"
        >
          {d.file_path} · lines {d.start_line}-{d.end_line}
        </p>
      </div>
      <div className="space-y-1.5 text-[12.5px]">
        <p>
          <span className="text-slate-500">Purpose: </span>
          <span className="text-slate-300">
            {d.docstring ||
              "No docstring - open in AI Workspace for an explanation."}
          </span>
        </p>
        {isFn && (
          <p>
            <span className="text-slate-500">Parameters: </span>
            <code className="font-mono text-sky-300">{d.params || "()"}</code>
          </p>
        )}
        {isFn && (
          <p>
            <span className="text-slate-500">Returns: </span>
            <span className="text-slate-300">
              {d.returns ||
                "not annotated - see return statements in the flowchart"}
            </span>
          </p>
        )}
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        <SmallBtn
          testId="expand-node-button"
          onClick={onExpand}
          icon={expanding ? Loader2 : ChevronsUpDown}
        >
          Expand
        </SmallBtn>
        <SmallBtn
          testId="collapse-node-button"
          onClick={onCollapse}
          icon={ChevronsDownUp}
        >
          {collapsed ? "Uncollapse" : "Collapse branch"}
        </SmallBtn>
        <SmallBtn
          testId="add-compare-button"
          onClick={onCompare}
          icon={GitCompareArrows}
          active={inCompare}
        >
          {inCompare ? "In compare" : "Add to compare"}
        </SmallBtn>
        {isFn && (
          <SmallBtn testId="show-flow-button" onClick={onFlow} icon={Workflow}>
            Execution flow
          </SmallBtn>
        )}
        <SmallBtn testId="center-node-button" onClick={onCenter} icon={Network}>
          Centre graph here
        </SmallBtn>
        <SmallBtn
          testId="open-workspace-button"
          onClick={onWorkspace}
          icon={Code2}
        >
          Open in Workspace
        </SmallBtn>
      </div>
      <button
        type="button"
        data-testid="simulate-remove-button"
        disabled={removed}
        onClick={onRemove}
        className="flex w-full items-center justify-center gap-1.5 rounded-md border border-red-500/40 bg-red-500/5 py-1.5 text-[12px] text-red-300 transition-colors hover:bg-red-500/15 disabled:opacity-50"
        title="Hide this node and analyse impact - your code is not modified"
      >
        <Trash2 className="h-3.5 w-3.5" />
        {removed ? "Removed in simulation" : "Simulate removal (visual only)"}
      </button>
      {list("Called by", d.callers, "node-callers")}
      {list("Calls", d.callees, "node-callees")}
      {d.external_calls.length > 0 && (
        <p className="text-[11.5px] text-slate-500">
          <span className="uppercase tracking-wider">
            External / unresolved calls:{" "}
          </span>
          <span className="font-mono">{d.external_calls.join(", ")}</span>
        </p>
      )}
      {d.related.length > 0 &&
        list("Related (same class)", d.related, "node-related")}
      <CodeBlock
        code={d.code}
        language={d.language}
        startLine={d.start_line}
        className="max-h-72"
        testId="node-code"
      />
    </div>
  );
}

function SmallBtn({
  children,
  icon: I,
  onClick,
  testId,
  active,
}: {
  children: React.ReactNode;
  icon: typeof X;
  onClick: () => void;
  testId: string;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-[11.5px] transition-colors",
        active
          ? "border-violet-500/60 bg-violet-500/15 text-violet-200"
          : "border-line text-slate-300 hover:border-blue-500/50 hover:text-white",
      )}
    >
      <I className={cn("h-3.5 w-3.5", I === Loader2 && "animate-spin")} />
      {children}
    </button>
  );
}

export default function Explorer() {
  return (
    <ReactFlowProvider>
      <ExplorerInner />
    </ReactFlowProvider>
  );
}
