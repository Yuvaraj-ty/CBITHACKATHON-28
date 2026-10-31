import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { motion } from "motion/react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Boxes,
  BrainCircuit,
  FolderGit2,
  GraduationCap,
  LogOut,
  Menu,
  Network,
  Plus,
  Settings,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { apiDelete } from "@/lib/api";
import { endSession } from "@/lib/session";
import {
  errMsg,
  useApp,
  useCurrentRepo,
  useMe,
  useRepos,
} from "@/lib/appState";
import type { RepoOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { UploadDialog } from "@/components/workspace/UploadDialog";
import { SettingsDialog } from "@/components/layout/SettingsDialog";

const UploadCtx = createContext<() => void>(() => {});
export const useOpenUpload = () => useContext(UploadCtx);

const NAV = [
  {
    to: "/",
    label: "AI Workspace",
    icon: BrainCircuit,
    testId: "nav-workspace",
  },
  {
    to: "/explorer",
    label: "Code Explorer",
    icon: Network,
    testId: "nav-explorer",
  },
  {
    to: "/learn",
    label: "Learning",
    icon: GraduationCap,
    testId: "nav-learning",
  },
];

export function RepoStatusBar({ repo }: { repo: RepoOut }) {
  const active = ["queued", "indexing"].includes(repo.status);
  return (
    <div className="mt-2">
      <div className="h-1 overflow-hidden rounded-full bg-slate-800">
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500",
            repo.status === "failed"
              ? "bg-red-500"
              : repo.status === "ready"
                ? "bg-emerald-500"
                : "bg-blue-500",
          )}
          style={{
            width: `${Math.round((repo.status === "failed" ? 1 : repo.progress) * 100)}%`,
          }}
        />
      </div>
      <p
        data-testid="repo-status-text"
        className={cn(
          "mt-1 text-[11px]",
          repo.status === "failed" ? "text-red-400" : "text-slate-500",
        )}
      >
        {active
          ? `${repo.stage ?? "Indexing"} · ${repo.files_indexed}/${repo.files_total || "?"} files`
          : repo.status === "failed"
            ? (repo.error ?? "Indexing failed")
            : `${repo.files_indexed} files · ${repo.symbol_count} symbols`}
      </p>
    </div>
  );
}

function SidebarBody({
  onUpload,
  onSettings,
  onNavigate,
}: {
  onUpload: () => void;
  onSettings: () => void;
  onNavigate?: () => void;
}) {
  const { repoId, setRepoId } = useApp();
  const { data: me } = useMe();
  const { data: repos = [] } = useRepos();
  const { data: current } = useCurrentRepo();
  const qc = useQueryClient();
  const [toRemove, setToRemove] = useState<RepoOut | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete(`/repos/${id}`),
    onSuccess: (_d, id) => {
      if (id === repoId) setRepoId(null);
      void qc.invalidateQueries({ queryKey: ["repos"] });
      toast.success("Repository removed from CodeAtlas");
      setToRemove(null);
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <div className="flex h-full flex-col justify-between gap-4 p-3">
      <div className="flex min-h-0 flex-col gap-5">
        <div className="flex items-center gap-2.5 px-2 pt-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 shadow-[0_0_20px_rgba(59,130,246,0.35)]">
            <Boxes className="h-4.5 w-4.5 text-white" />
          </div>
          <div>
            <p className="text-[15px] font-semibold tracking-tight text-slate-100">
              CodeAtlas
            </p>
            <p className="text-[10.5px] text-slate-500">
              Repository intelligence
            </p>
          </div>
        </div>
        <nav className="flex flex-col gap-0.5">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              data-testid={n.testId}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13.5px] transition-colors duration-150",
                  isActive
                    ? "bg-slate-800/80 text-sky-300"
                    : "text-slate-400 hover:bg-slate-800/40 hover:text-slate-200",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-sky-400"
                    />
                  )}
                  <n.icon className="h-4 w-4" />
                  {n.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div
          data-testid="current-repo-indicator"
          className="rounded-lg border border-line bg-panel/60 p-3"
        >
          <p className="text-[10.5px] font-medium uppercase tracking-wider text-slate-500">
            Current repository
          </p>
          {current ? (
            <>
              <p
                data-testid="current-repo-name"
                className="mt-1 truncate text-[13px] font-medium text-slate-200"
                title={current.name}
              >
                {current.name}
              </p>
              {current.is_sample && (
                <span className="mt-1 inline-block rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-300">
                  Sample project
                </span>
              )}
              <RepoStatusBar repo={current} />
            </>
          ) : (
            <p className="mt-1 text-[12.5px] text-slate-500">
              None loaded - general questions only
            </p>
          )}
          <Button
            data-testid="sidebar-upload-button"
            size="sm"
            variant="outline"
            className="mt-2.5 w-full gap-1.5"
            onClick={onUpload}
          >
            <Upload className="h-3.5 w-3.5" /> Upload repository
          </Button>
        </div>
        <div className="flex min-h-0 flex-col">
          <p className="mb-1.5 px-2 text-[10.5px] font-medium uppercase tracking-wider text-slate-500">
            Recent repositories
          </p>
          <div className="scroll-thin flex max-h-56 flex-col gap-0.5 overflow-y-auto">
            {repos.length === 0 && (
              <p className="px-2 text-[12px] text-slate-600">
                Nothing uploaded yet
              </p>
            )}
            {repos.map((r) => (
              <div
                key={r.id}
                className={cn(
                  "group flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors",
                  r.id === repoId ? "bg-slate-800/60" : "hover:bg-slate-800/40",
                )}
              >
                <button
                  type="button"
                  data-testid={`recent-repo-${r.id}`}
                  onClick={() => {
                    setRepoId(r.id);
                    onNavigate?.();
                  }}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                >
                  <FolderGit2
                    className={cn(
                      "h-3.5 w-3.5 shrink-0",
                      r.status === "failed"
                        ? "text-red-400"
                        : r.id === repoId
                          ? "text-sky-400"
                          : "text-slate-500",
                    )}
                  />
                  <span className="truncate text-[12.5px] text-slate-300">
                    {r.name}
                  </span>
                </button>
                <button
                  type="button"
                  data-testid={`remove-repo-${r.id}`}
                  title="Remove repository"
                  onClick={() => setToRemove(r)}
                  className="opacity-0 transition-opacity group-hover:opacity-100 text-slate-500 hover:text-red-400"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={onUpload}
            data-testid="sidebar-new-repo"
            className="mt-1 flex items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] text-slate-500 transition-colors hover:text-slate-300"
          >
            <Plus className="h-3.5 w-3.5" /> Add another
          </button>
        </div>
      </div>
      <div className="flex flex-col gap-1 border-t border-line pt-3">
        <button
          type="button"
          data-testid="settings-button"
          onClick={onSettings}
          className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-slate-400 transition-colors hover:bg-slate-800/40 hover:text-slate-200"
        >
          <Settings className="h-4 w-4" /> Settings
        </button>
        <div className="flex items-center gap-2.5 rounded-md px-2 py-1.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-800 text-[12px] font-semibold text-sky-300">
            {me?.name?.[0]?.toUpperCase() ?? "?"}
          </div>
          <div className="min-w-0 flex-1">
            <p
              data-testid="profile-name"
              className="truncate text-[12.5px] font-medium text-slate-200"
            >
              {me?.name}
            </p>
            <p className="truncate text-[11px] text-slate-500">{me?.email}</p>
          </div>
          <button
            type="button"
            data-testid="logout-button"
            title="Sign out"
            onClick={() => void endSession()}
            className="text-slate-500 transition-colors hover:text-slate-200"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
      <Dialog open={!!toRemove} onOpenChange={(o) => !o && setToRemove(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove {toRemove?.name}?</DialogTitle>
            <DialogDescription>
              This deletes CodeAtlas's index of the repository (files, symbols,
              search index). Your original source is never touched.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setToRemove(null)}>
              Cancel
            </Button>
            <Button
              data-testid="confirm-remove-repo"
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => toRemove && remove.mutate(toRemove.id)}
            >
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function AppShell({ children }: { children?: ReactNode }) {
  const [upload, setUpload] = useState(false);
  const [settings, setSettings] = useState(false);
  const [mobile, setMobile] = useState(false);
  const location = useLocation();
  const { data: current } = useCurrentRepo();
  const qc = useQueryClient();
  const prev = useRef<string | null>(null);
  useEffect(() => {
    if (!current) return;
    const key = `${current.id}:${current.status}`;
    if (
      prev.current &&
      prev.current.startsWith(current.id) &&
      prev.current !== key
    ) {
      if (current.status === "ready")
        toast.success(
          `${current.name} indexed: ${current.files_indexed} files, ${current.symbol_count} symbols`,
        );
      if (current.status === "failed")
        toast.error(`Indexing failed: ${current.error ?? "unknown error"}`);
      void qc.invalidateQueries({ queryKey: ["repos"] });
    }
    prev.current = key;
  }, [current, qc]);

  return (
    <UploadCtx.Provider value={() => setUpload(true)}>
      <div className="flex h-screen w-screen overflow-hidden bg-page text-slate-200">
        <aside className="hidden w-64 shrink-0 border-r border-line bg-rail md:block">
          <SidebarBody
            onUpload={() => setUpload(true)}
            onSettings={() => setSettings(true)}
          />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2 border-b border-line bg-rail px-3 py-2 md:hidden">
            <button
              type="button"
              data-testid="mobile-menu-button"
              onClick={() => setMobile(true)}
              className="text-slate-300"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="text-sm font-semibold">CodeAtlas</span>
          </div>
          <motion.main
            key={location.pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="flex min-h-0 flex-1 flex-col"
          >
            {children ?? <Outlet />}
          </motion.main>
        </div>
        <Sheet open={mobile} onOpenChange={setMobile}>
          <SheetContent side="left" className="w-72 bg-rail p-0">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <SidebarBody
              onUpload={() => {
                setMobile(false);
                setUpload(true);
              }}
              onSettings={() => {
                setMobile(false);
                setSettings(true);
              }}
              onNavigate={() => setMobile(false)}
            />
          </SheetContent>
        </Sheet>
        <UploadDialog open={upload} onOpenChange={setUpload} />
        <SettingsDialog open={settings} onOpenChange={setSettings} />
      </div>
    </UploadCtx.Provider>
  );
}
