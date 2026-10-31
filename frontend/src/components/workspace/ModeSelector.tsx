import { motion } from "motion/react";
import { GraduationCap, Sparkles, Zap } from "lucide-react";
import type { Mode } from "@/lib/types";
import { cn } from "@/lib/utils";

const MODES: {
  id: Mode;
  label: string;
  icon: typeof Zap;
  hint: string;
  color: string;
}[] = [
  {
    id: "beginner",
    label: "Beginner",
    icon: Sparkles,
    hint: "Simple language, analogies, small steps",
    color: "text-emerald-300",
  },
  {
    id: "student",
    label: "Student",
    icon: GraduationCap,
    hint: "Concepts + implementation details",
    color: "text-blue-300",
  },
  {
    id: "expert",
    label: "Expert",
    icon: Zap,
    hint: "Concise, architecture, edge cases",
    color: "text-violet-300",
  },
];

export function ModeSelector({
  value,
  onChange,
}: {
  value: Mode;
  onChange: (m: Mode) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Explanation mode"
      className="inline-flex rounded-lg border border-line bg-editor p-0.5"
    >
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          role="radio"
          aria-checked={value === m.id}
          title={m.hint}
          data-testid={`mode-selector-${m.id}`}
          onClick={() => onChange(m.id)}
          className={cn(
            "relative flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12.5px] transition-colors duration-150",
            value === m.id ? m.color : "text-slate-500 hover:text-slate-300",
          )}
        >
          {value === m.id && (
            <motion.span
              layoutId="mode-pill"
              className="absolute inset-0 rounded-md bg-slate-800"
              transition={{ duration: 0.18 }}
            />
          )}
          <m.icon className="relative h-3.5 w-3.5" />
          <span className="relative">{m.label}</span>
        </button>
      ))}
    </div>
  );
}
