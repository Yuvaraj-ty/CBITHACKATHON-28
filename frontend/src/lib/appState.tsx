import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, ApiError } from "@/lib/api";
import type {
  Mode,
  RepoOut,
  Selection,
  SystemStatus,
  UserOut,
} from "@/lib/types";

// Shared cross-page state: current repo, selected file/symbol/selection, AI mode. Persisted per browser.
interface Focus {
  path: string;
  start: number;
  end: number;
  nonce: number;
}
interface AppState {
  repoId: string | null;
  mode: Mode;
  selectedFile: string | null;
  selectedSymbolId: string | null;
  selection: Selection | null;
  conversationId: string | null;
  focus: Focus | null;
  setRepoId: (id: string | null) => void;
  setMode: (m: Mode) => void;
  openFile: (path: string, start?: number, end?: number) => void;
  setSelectedSymbolId: (id: string | null) => void;
  setSelection: (s: Selection | null) => void;
  setConversationId: (id: string | null) => void;
}

const Ctx = createContext<AppState | null>(null);
const KEY = "codeatlas-state-v1";

type Persisted = Pick<
  AppState,
  | "repoId"
  | "mode"
  | "selectedFile"
  | "selectedSymbolId"
  | "selection"
  | "conversationId"
>;

function load(): Persisted {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw)
      return {
        repoId: null,
        mode: "student",
        selectedFile: null,
        selectedSymbolId: null,
        selection: null,
        conversationId: null,
        ...JSON.parse(raw),
      };
  } catch {
    /* ignore corrupt state */
  }
  return {
    repoId: null,
    mode: "student",
    selectedFile: null,
    selectedSymbolId: null,
    selection: null,
    conversationId: null,
  };
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState<Persisted>(load);
  const [focus, setFocus] = useState<Focus | null>(null);
  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(s));
  }, [s]);

  const setRepoId = useCallback(
    (repoId: string | null) =>
      setS((p) =>
        p.repoId === repoId
          ? p
          : {
              ...p,
              repoId,
              selectedFile: null,
              selectedSymbolId: null,
              selection: null,
              conversationId: null,
            },
      ),
    [],
  );
  const setMode = useCallback(
    (mode: Mode) => setS((p) => ({ ...p, mode })),
    [],
  );
  const openFile = useCallback((path: string, start?: number, end?: number) => {
    setS((p) => ({ ...p, selectedFile: path }));
    setFocus(
      start ? { path, start, end: end ?? start, nonce: Date.now() } : null,
    );
  }, []);
  const setSelectedSymbolId = useCallback(
    (selectedSymbolId: string | null) =>
      setS((p) => ({ ...p, selectedSymbolId })),
    [],
  );
  const setSelection = useCallback(
    (selection: Selection | null) => setS((p) => ({ ...p, selection })),
    [],
  );
  const setConversationId = useCallback(
    (conversationId: string | null) => setS((p) => ({ ...p, conversationId })),
    [],
  );

  const value = useMemo<AppState>(
    () => ({
      ...s,
      focus,
      setRepoId,
      setMode,
      openFile,
      setSelectedSymbolId,
      setSelection,
      setConversationId,
    }),
    [
      s,
      focus,
      setRepoId,
      setMode,
      openFile,
      setSelectedSymbolId,
      setSelection,
      setConversationId,
    ],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside AppStateProvider");
  return v;
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiGet<UserOut>("/auth/me"),
    retry: false,
    staleTime: 60_000,
  });
}

export function useRepos() {
  return useQuery({
    queryKey: ["repos"],
    queryFn: () => apiGet<RepoOut[]>("/repos"),
  });
}

export function useCurrentRepo() {
  const { repoId } = useApp();
  return useQuery({
    queryKey: ["repo", repoId],
    queryFn: () => apiGet<RepoOut>(`/repos/${repoId}`),
    enabled: !!repoId,
    refetchInterval: (q) =>
      q.state.data && ["queued", "indexing"].includes(q.state.data.status)
        ? 1200
        : false,
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system"],
    queryFn: () => apiGet<SystemStatus>("/system/status"),
    staleTime: 300_000,
  });
}

export function errMsg(e: unknown): string {
  if (e instanceof ApiError) {
    const b = e.body as { detail?: unknown } | null;
    if (typeof b?.detail === "string") return b.detail;
    if (Array.isArray(b?.detail))
      return (b.detail as { msg?: string }[]).map((d) => d.msg).join("; ");
    return `Request failed (${e.status})`;
  }
  return e instanceof Error ? e.message : "Something went wrong";
}
