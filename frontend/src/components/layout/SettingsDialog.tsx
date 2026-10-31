import { Bot, Cpu, Languages, Search } from "lucide-react";
import { useApp, useMe, useSystemStatus } from "@/lib/appState";
import type { Mode } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ModeSelector } from "@/components/workspace/ModeSelector";

export function SettingsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const { data: sys } = useSystemStatus();
  const { data: me } = useMe();
  const { mode, setMode } = useApp();
  const provider =
    sys?.provider === "gemini"
      ? "Google Gemini"
      : sys?.provider === "claude" || sys?.provider === "anthropic"
        ? "Anthropic (Claude)"
        : sys?.provider === "featherless"
          ? "Featherless AI"
          : sys?.provider === "emergent"
            ? "Emergent Universal Key (fallback)"
            : "Not configured";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="settings-dialog">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>Signed in as {me?.email}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-[13px]">
          <div>
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-slate-500">
              Default explanation mode
            </p>
            <ModeSelector value={mode} onChange={(m: Mode) => setMode(m)} />
          </div>
          <div className="space-y-2.5 rounded-lg border border-line bg-panel/50 p-3">
            <Row
              icon={<Bot className="h-4 w-4" />}
              label="AI provider"
              value={provider}
              testId="settings-ai-provider"
              warn={!sys?.configured}
            />
            <Row
              icon={<Cpu className="h-4 w-4" />}
              label="Model"
              value={sys?.model || "-"}
              testId="settings-ai-model"
            />
            <Row
              icon={<Search className="h-4 w-4" />}
              label="Semantic search"
              value={sys?.embedding ?? "-"}
            />
            <Row
              icon={<Languages className="h-4 w-4" />}
              label="Symbol parsing (tree-sitter)"
              value={sys?.parsed_languages.join(", ") ?? "-"}
            />
          </div>
          {!sys?.configured && (
            <p className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-[12px] text-amber-200">
              No AI provider is configured. Add ANTHROPIC_API_KEY or FEATHERLESS_API_KEY in backend/.env to enable AI answers.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Row({
  icon,
  label,
  value,
  testId,
  warn,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  testId?: string;
  warn?: boolean;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <span className="mt-0.5 text-slate-500">{icon}</span>
      <div className="min-w-0">
        <p className="text-[11px] text-slate-500">{label}</p>
        <p
          data-testid={testId}
          className={warn ? "text-amber-300" : "text-slate-200"}
        >
          {value}
        </p>
      </div>
    </div>
  );
}
