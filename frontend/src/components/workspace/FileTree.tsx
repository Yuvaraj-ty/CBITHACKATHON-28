import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  FileText,
  Folder,
  FolderOpen,
  Search,
} from "lucide-react";
import { apiGet } from "@/lib/api";
import { useApp } from "@/lib/appState";
import type { FileEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Node {
  name: string;
  path: string;
  children: Map<string, Node>;
  file?: FileEntry;
}

function build(files: FileEntry[]): Node {
  const root: Node = { name: "", path: "", children: new Map() };
  for (const f of files) {
    const parts = f.path.split("/");
    let cur = root;
    parts.forEach((p, i) => {
      const path = parts.slice(0, i + 1).join("/");
      if (!cur.children.has(p))
        cur.children.set(p, { name: p, path, children: new Map() });
      cur = cur.children.get(p)!;
      if (i === parts.length - 1) cur.file = f;
    });
  }
  return root;
}

function sorted(n: Node): Node[] {
  return [...n.children.values()].sort(
    (a, b) =>
      (a.file ? 1 : 0) - (b.file ? 1 : 0) || a.name.localeCompare(b.name),
  );
}

export function FileTree({ repoId }: { repoId: string }) {
  const { selectedFile, openFile } = useApp();
  const [q, setQ] = useState("");
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const { data: files, isLoading } = useQuery({
    queryKey: ["files", repoId],
    queryFn: () => apiGet<FileEntry[]>(`/repos/${repoId}/files`),
  });
  const filtered = useMemo(
    () =>
      (files ?? []).filter((f) =>
        f.path.toLowerCase().includes(q.toLowerCase()),
      ),
    [files, q],
  );
  const tree = useMemo(() => build(filtered), [filtered]);
  const toggle = (p: string) =>
    setClosed((s) => {
      const n = new Set(s);
      if (n.has(p)) n.delete(p);
      else n.add(p);
      return n;
    });

  const render = (node: Node, depth: number) =>
    sorted(node).map((c) => {
      if (c.file) {
        const active = selectedFile === c.path;
        return (
          <button
            key={c.path}
            type="button"
            data-testid={`file-tree-item-${c.path}`}
            onClick={() => openFile(c.path)}
            title={c.path}
            className={cn(
              "flex w-full items-center gap-1.5 rounded px-1.5 py-[3px] text-left text-[12.5px] transition-colors duration-100",
              active
                ? "bg-blue-500/15 text-sky-200"
                : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200",
            )}
            style={{ paddingLeft: depth * 12 + 6 }}
          >
            {c.file.parsed ? (
              <FileCode2 className="h-3.5 w-3.5 shrink-0 text-sky-500/80" />
            ) : (
              <FileText className="h-3.5 w-3.5 shrink-0 text-slate-600" />
            )}
            <span className="truncate">{c.name}</span>
          </button>
        );
      }
      const open = q ? true : !closed.has(c.path);
      return (
        <div key={c.path}>
          <button
            type="button"
            data-testid={`file-tree-folder-${c.path}`}
            onClick={() => toggle(c.path)}
            className="flex w-full items-center gap-1 rounded px-1.5 py-[3px] text-left text-[12.5px] text-slate-300 transition-colors hover:bg-slate-800/50"
            style={{ paddingLeft: depth * 12 + 2 }}
          >
            {open ? (
              <ChevronDown className="h-3 w-3 text-slate-500" />
            ) : (
              <ChevronRight className="h-3 w-3 text-slate-500" />
            )}
            {open ? (
              <FolderOpen className="h-3.5 w-3.5 text-amber-400/80" />
            ) : (
              <Folder className="h-3.5 w-3.5 text-amber-400/80" />
            )}
            <span className="truncate">{c.name}</span>
          </button>
          {open && render(c, depth + 1)}
        </div>
      );
    });

  return (
    <div className="flex h-full flex-col">
      <div className="relative p-2">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
        <input
          data-testid="file-search-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search files"
          className="h-8 w-full rounded-md border border-line bg-editor pl-7 pr-2 text-[12.5px] text-slate-200 outline-none transition-colors placeholder:text-slate-600 focus:border-blue-500/60"
        />
      </div>
      <div
        className="scroll-thin min-h-0 flex-1 overflow-y-auto px-1.5 pb-3"
        data-testid="file-tree"
      >
        {isLoading &&
          Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="skeleton mx-1 my-1.5 h-4"
              style={{ width: `${50 + ((i * 17) % 40)}%` }}
            />
          ))}
        {files && filtered.length === 0 && (
          <p className="px-2 py-3 text-[12px] text-slate-600">
            No files match "{q}"
          </p>
        )}
        {render(tree, 0)}
      </div>
      {files && (
        <p className="border-t border-line px-3 py-1.5 text-[11px] text-slate-600">
          {files.length} files ·{" "}
          <FileCode2 className="inline h-3 w-3 text-sky-500/80" /> = parsed
          symbols
        </p>
      )}
    </div>
  );
}
