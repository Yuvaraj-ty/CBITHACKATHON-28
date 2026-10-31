import { Fragment, type ReactNode } from "react";
import { CodeBlock } from "@/components/CodeBlock";

// Minimal, safe Markdown renderer (no HTML injection): headings, lists, code fences, bold, inline code, [E1] citations.
function inline(text: string, onCite?: (id: string) => void): ReactNode[] {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[E\d+\])/g);
  return parts.map((p, i) => {
    if (p.startsWith("`") && p.endsWith("`") && p.length > 2)
      return (
        <code
          key={i}
          className="rounded bg-slate-800/80 px-1 py-0.5 font-mono text-[0.85em] text-sky-300"
        >
          {p.slice(1, -1)}
        </code>
      );
    if (p.startsWith("**") && p.endsWith("**"))
      return (
        <strong key={i} className="font-semibold text-slate-100">
          {p.slice(2, -2)}
        </strong>
      );
    const cite = p.match(/^\[(E\d+)\]$/);
    if (cite)
      return (
        <button
          key={i}
          type="button"
          data-testid={`citation-${cite[1]}`}
          onClick={() => onCite?.(cite[1])}
          className="mx-0.5 inline-flex items-center rounded border border-blue-500/40 bg-blue-500/10 px-1 font-mono text-[11px] text-blue-300 transition-colors hover:bg-blue-500/25"
        >
          {cite[1]}
        </button>
      );
    return <Fragment key={i}>{p}</Fragment>;
  });
}

export function Markdown({
  text,
  onCite,
}: {
  text: string;
  onCite?: (id: string) => void;
}) {
  const lines = text.split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const fence = line.match(/^```(\w+)?/);
    if (fence) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```"))
        buf.push(lines[i++]);
      i++;
      out.push(
        <CodeBlock
          key={out.length}
          code={buf.join("\n")}
          language={fence[1]}
          className="my-2 max-h-96"
        />,
      );
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)/);
    if (h) {
      out.push(
        <p
          key={out.length}
          className={
            h[1].length <= 2
              ? "mt-3 mb-1 text-[15px] font-semibold text-slate-100"
              : "mt-2 mb-1 text-sm font-semibold text-slate-200"
          }
        >
          {inline(h[2], onCite)}
        </p>,
      );
      i++;
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const items: { ordered: boolean; text: string; indent: number }[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        const m = lines[i].match(/^(\s*)([-*]|\d+\.)\s+(.*)/)!;
        items.push({
          ordered: /\d/.test(m[2]),
          text: m[3],
          indent: m[1].length,
        });
        i++;
      }
      out.push(
        <ul key={out.length} className="my-1.5 space-y-1">
          {items.map((it, k) => (
            <li
              key={k}
              className="flex gap-2"
              style={{ paddingLeft: it.indent * 6 }}
            >
              <span className="mt-[1px] shrink-0 text-slate-500">
                {it.ordered ? `${k + 1}.` : "•"}
              </span>
              <span>{inline(it.text, onCite)}</span>
            </li>
          ))}
        </ul>,
      );
      continue;
    }
    if (/^---+$/.test(line.trim())) {
      out.push(<hr key={out.length} className="my-3 border-line" />);
      i++;
      continue;
    }
    if (line.trim())
      out.push(
        <p key={out.length} className="my-1.5">
          {inline(line, onCite)}
        </p>,
      );
    i++;
  }
  return (
    <div className="text-[14px] leading-relaxed text-slate-300">{out}</div>
  );
}
