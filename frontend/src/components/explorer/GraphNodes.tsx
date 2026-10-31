import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  CircleDot,
  CornerDownLeft,
  GitBranch,
  Play,
  Repeat,
  Square,
  SquareFunction,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { FlowNode, SymbolSummary } from "@/lib/types";

export interface SymbolNodeData extends Record<string, unknown> {
  sym: SymbolSummary;
  root?: boolean;
  selected?: boolean;
  removed?: boolean;
  affected?: "direct" | "transitive" | "orphaned";
  compareIndex?: number;
  collapsedCount?: number;
}

const KIND: Record<string, { badge: string; ring: string }> = {
  function: { badge: "bg-sky-500/15 text-sky-300", ring: "border-sky-500/40" },
  method: { badge: "bg-blue-500/15 text-blue-300", ring: "border-blue-500/40" },
  class: {
    badge: "bg-violet-500/20 text-violet-300",
    ring: "border-violet-500/50",
  },
  interface: {
    badge: "bg-fuchsia-500/15 text-fuchsia-300",
    ring: "border-fuchsia-500/40",
  },
  struct: {
    badge: "bg-violet-500/20 text-violet-300",
    ring: "border-violet-500/50",
  },
};

export function SymbolNode({ data }: NodeProps) {
  const d = data as SymbolNodeData;
  const k = KIND[d.sym.kind] ?? KIND.function;
  return (
    <div
      data-testid={`graph-node-${d.sym.name}`}
      className={cn(
        "w-[220px] rounded-lg border bg-[#0F172A] px-3 py-2 shadow-lg transition-[border-color,box-shadow,opacity] duration-150",
        d.sym.kind === "class" ||
          d.sym.kind === "interface" ||
          d.sym.kind === "struct"
          ? "rounded-xl border-dashed"
          : "",
        k.ring,
        d.root && "shadow-[0_0_0_1px_#38BDF8,0_0_24px_rgba(56,189,248,0.25)]",
        d.selected && "border-sky-400",
        d.affected === "direct" &&
          "border-orange-500 shadow-[0_0_18px_rgba(249,115,22,0.35)]",
        d.affected === "transitive" && "border-amber-400/80",
        d.affected === "orphaned" && "border-yellow-300/70 border-dashed",
        d.removed && "border-red-500/70 opacity-40",
        d.sym.is_test && !d.affected && "border-emerald-500/40",
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2 !w-2 !border-slate-600 !bg-slate-800"
      />
      <div className="flex items-center gap-1.5">
        <span
          className={cn(
            "rounded px-1 py-[1px] text-[9.5px] font-semibold uppercase tracking-wider",
            k.badge,
          )}
        >
          {d.sym.kind}
        </span>
        {d.sym.is_test && (
          <span className="rounded bg-emerald-500/15 px-1 py-[1px] text-[9.5px] text-emerald-300">
            test
          </span>
        )}
        {d.compareIndex && (
          <span className="ml-auto rounded bg-violet-600 px-1.5 text-[10px] font-bold text-white">
            {d.compareIndex === 1 ? "A" : "B"}
          </span>
        )}
      </div>
      <p
        className={cn(
          "mt-1 truncate font-mono text-[13px] text-slate-100",
          d.removed && "line-through",
        )}
      >
        {d.sym.parent && d.sym.kind === "method" ? (
          <span className="text-slate-500">{d.sym.parent}.</span>
        ) : null}
        {d.sym.name}()
      </p>
      <p className="truncate font-mono text-[10.5px] text-slate-500">
        {d.sym.file_path}:{d.sym.start_line}-{d.sym.end_line}
      </p>
      <div className="mt-1 flex gap-2 text-[10px] text-slate-500">
        <span title="Callers">← {d.sym.callers_count}</span>
        <span title="Callees">→ {d.sym.callees_count}</span>
        {d.collapsedCount ? (
          <span className="ml-auto rounded bg-slate-700 px-1 text-slate-200">
            +{d.collapsedCount} hidden
          </span>
        ) : null}
        {d.removed && (
          <span className="ml-auto text-red-400">removed (simulated)</span>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2 !w-2 !border-slate-600 !bg-slate-800"
      />
    </div>
  );
}

const FLOW: Record<string, { cls: string; icon: typeof Play; tag: string }> = {
  start: {
    cls: "rounded-full border-emerald-500/60 bg-emerald-950/60 text-emerald-200",
    icon: Play,
    tag: "start",
  },
  end: {
    cls: "rounded-full border-slate-500/60 bg-slate-900 text-slate-300",
    icon: Square,
    tag: "end",
  },
  condition: {
    cls: "rounded-md border-amber-500/60 bg-amber-950/40 text-amber-100 [clip-path:polygon(6%_0,94%_0,100%_50%,94%_100%,6%_100%,0_50%)] px-6",
    icon: GitBranch,
    tag: "condition",
  },
  loop: {
    cls: "rounded-xl border-violet-500/60 bg-violet-950/40 text-violet-100",
    icon: Repeat,
    tag: "loop",
  },
  return: {
    cls: "rounded-md border-red-500/50 bg-red-950/30 text-red-100",
    icon: CornerDownLeft,
    tag: "return",
  },
  call: {
    cls: "rounded-md border-blue-500/50 bg-blue-950/40 text-blue-100",
    icon: SquareFunction,
    tag: "call",
  },
  step: {
    cls: "rounded-md border-slate-600 bg-[#0F172A] text-slate-200",
    icon: CircleDot,
    tag: "step",
  },
};

export function FlowNodeView({ data }: NodeProps) {
  const n = (data as { node: FlowNode; active?: boolean }).node;
  const active = (data as { active?: boolean }).active;
  const f = FLOW[n.kind] ?? FLOW.step;
  return (
    <div
      data-testid={`flow-node-${n.id}`}
      className={cn(
        "w-[240px] border px-3 py-2 shadow-md transition-shadow",
        f.cls,
        active && "shadow-[0_0_0_2px_#38BDF8]",
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-1.5 !w-1.5 !bg-slate-600"
      />
      <div className="flex items-center gap-1.5 text-[9.5px] uppercase tracking-wider opacity-70">
        <f.icon className="h-3 w-3" />
        {f.tag}
        <span className="ml-auto font-mono normal-case">
          L{n.start_line}
          {n.end_line !== n.start_line ? `-${n.end_line}` : ""}
        </span>
      </div>
      <p className="mt-0.5 break-words font-mono text-[11.5px] leading-snug">
        {n.label}
      </p>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !bg-slate-600"
      />
    </div>
  );
}

export const nodeTypes = { symbol: SymbolNode, flow: FlowNodeView };
