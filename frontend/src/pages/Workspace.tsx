import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import {
  Bot,
  FileCode2,
  FolderTree,
  History,
  Loader2,
  MessageSquarePlus,
  MousePointerSquareDashed,
  PanelLeftClose,
  PanelLeftOpen,
  SendHorizontal,
  Upload,
  Wand2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";
import { errMsg, useApp, useCurrentRepo } from "@/lib/appState";
import type {
  ChatOut,
  ConversationOut,
  Evidence,
  MessageOut,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Markdown } from "@/components/Markdown";
import { ModeSelector } from "@/components/workspace/ModeSelector";
import { FileTree } from "@/components/workspace/FileTree";
import {
  ConfidenceMeter,
  EvidencePanel,
} from "@/components/workspace/EvidencePanel";
import { SourcePanel } from "@/components/workspace/SourcePanel";
import { AlternativesDialog } from "@/components/workspace/ToolDialogs";
import { useOpenUpload } from "@/components/layout/AppShell";

type Scope = "auto" | "general" | "repo";
const SCOPES: Record<Scope, string> = {
  auto: "Auto-detect",
  general: "General only",
  repo: "Repository",
};
const GENERAL_EXAMPLES = [
  "What is recursion?",
  "Explain object-oriented programming",
  "What is the difference between a stack and a queue?",
  "What is a linked list?",
];
const REPO_EXAMPLES = [
  "Where is authentication implemented?",
  "Explain how the login system works",
  "Which function handles user registration?",
  "Which files are responsible for database operations?",
];
const SCOPE_BADGE: Record<string, { label: string; cls: string }> = {
  general: {
    label: "General answer · repository not searched",
    cls: "border-slate-700 text-slate-400",
  },
  repo: {
    label: "Grounded in repository evidence",
    cls: "border-blue-500/40 text-blue-300",
  },
  selection: {
    label: "Scoped to your selection",
    cls: "border-violet-500/40 text-violet-300",
  },
  file: { label: "Scoped to file", cls: "border-sky-500/40 text-sky-300" },
};

export default function Workspace() {
  const {
    repoId,
    mode,
    setMode,
    selection,
    setSelection,
    conversationId,
    setConversationId,
    openFile,
  } = useApp();
  const { data: repo } = useCurrentRepo();
  const ready = repo?.status === "ready";
  const openUpload = useOpenUpload();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"evidence" | "source">("evidence");
  const [treeOpen, setTreeOpen] = useState(true);
  const [scope, setScope] = useState<Scope>("auto");
  const [fileCtx, setFileCtx] = useState<string | null>(null);
  const [activeMsg, setActiveMsg] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [altConcept, setAltConcept] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const msgs = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () =>
      apiGet<MessageOut[]>(`/conversations/${conversationId}/messages`),
    enabled: !!conversationId,
  });
  const convs = useQuery({
    queryKey: ["conversations"],
    queryFn: () => apiGet<ConversationOut[]>("/conversations"),
  });
  const messages = useMemo(
    () => (conversationId ? (msgs.data ?? []) : []),
    [conversationId, msgs.data],
  );

  const send = useMutation({
    mutationFn: (message: string) =>
      apiPost<ChatOut>("/chat", {
        message,
        mode,
        scope,
        conversation_id: conversationId,
        repo_id: ready ? repoId : null,
        selection: ready && selection ? selection : null,
        file_path: ready && !selection ? fileCtx : null,
      }),
    onSuccess: (d) => {
      qc.setQueryData<MessageOut[]>(["messages", d.conversation_id], (old) => [
        ...(old ?? []),
        d.user_message,
        d.reply,
      ]);
      if (d.conversation_id !== conversationId)
        setConversationId(d.conversation_id);
      void qc.invalidateQueries({ queryKey: ["conversations"] });
      setActiveMsg(d.reply.id);
      if (d.reply.evidence.length) setTab("evidence");
    },
    onError: (e, message) => {
      toast.error(errMsg(e));
      setText(message);
    },
  });

  useEffect(() => {
    void endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, send.isPending]);
  const active =
    messages.find((m) => m.id === activeMsg) ??
    [...messages].reverse().find((m) => m.role === "assistant");

  const submit = (msg?: string) => {
    const m = (msg ?? text).trim();
    if (!m || send.isPending) return;
    setText("");
    send.mutate(m);
  };
  const openEvidence = (e: Evidence) => {
    openFile(e.file_path, e.start_line, e.end_line);
    setTab("source");
  };
  const cite = (m: MessageOut, id: string) => {
    setActiveMsg(m.id);
    setTab("evidence");
    setTimeout(
      () =>
        document
          .getElementById(`evidence-${id}`)
          ?.scrollIntoView({ behavior: "smooth", block: "start" }),
      80,
    );
  };
  const newConversation = () => {
    setConversationId(null);
    setActiveMsg(null);
    setFileCtx(null);
    inputRef.current?.focus();
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-page px-4 py-2.5">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            AI Workspace
          </p>
          <p
            data-testid="workspace-repo-name"
            className="truncate text-[14px] font-medium text-slate-100"
          >
            {repo ? repo.name : "No repository - general programming chat"}
            {repo && Object.keys(repo.languages).length > 0 && (
              <span className="ml-2 text-[11.5px] font-normal text-slate-500">
                {Object.keys(repo.languages).join(" · ")}
              </span>
            )}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <ModeSelector value={mode} onChange={setMode} />
          <Select
            value={scope}
            onValueChange={(v: string) => setScope(v as Scope)}
          >
            <SelectTrigger
              size="sm"
              className="w-36"
              data-testid="scope-select"
              title="Whether to search the repository"
            >
              <SelectValue>{(v) => SCOPES[v as Scope]}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(SCOPES) as Scope[]).map((s) => (
                <SelectItem key={s} value={s} data-testid={`scope-option-${s}`}>
                  {SCOPES[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="conversation-history-button"
                />
              }
            >
              <History className="h-3.5 w-3.5" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-72">
              <DropdownMenuLabel>Recent conversations</DropdownMenuLabel>
              {(convs.data ?? []).length === 0 && (
                <p className="px-2 py-1.5 text-[12px] text-slate-500">
                  No conversations yet
                </p>
              )}
              {(convs.data ?? []).map((c) => (
                <DropdownMenuItem
                  key={c.id}
                  onClick={() => {
                    setConversationId(c.id);
                    setActiveMsg(null);
                  }}
                >
                  <span className="truncate">{c.title}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant="outline"
            size="sm"
            data-testid="new-conversation-button"
            onClick={newConversation}
          >
            <MessageSquarePlus className="h-3.5 w-3.5" /> New
          </Button>
          <Button
            size="sm"
            data-testid="header-upload-button"
            onClick={openUpload}
          >
            <Upload className="h-3.5 w-3.5" /> Upload repo
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {repo && ready && (
          <div
            className={cn(
              "hidden shrink-0 border-r border-line bg-[#0A0F18] transition-[width] duration-200 lg:block",
              treeOpen ? "w-60" : "w-10",
            )}
          >
            {treeOpen ? (
              <div className="flex h-full flex-col">
                <div className="flex items-center justify-between px-3 pt-2.5">
                  <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                    <FolderTree className="h-3.5 w-3.5" /> Files
                  </p>
                  <button
                    type="button"
                    data-testid="toggle-file-tree"
                    onClick={() => setTreeOpen(false)}
                    className="text-slate-500 hover:text-slate-200"
                  >
                    <PanelLeftClose className="h-4 w-4" />
                  </button>
                </div>
                <div
                  className="min-h-0 flex-1"
                  onClick={(e) =>
                    (e.target as HTMLElement).closest(
                      "[data-testid^='file-tree-item']",
                    ) && setTab("source")
                  }
                >
                  <FileTree repoId={repo.id} />
                </div>
              </div>
            ) : (
              <button
                type="button"
                data-testid="toggle-file-tree"
                onClick={() => setTreeOpen(true)}
                className="m-2 text-slate-500 hover:text-slate-200"
                title="Show files"
              >
                <PanelLeftOpen className="h-4 w-4" />
              </button>
            )}
          </div>
        )}

        <section className="flex min-h-[420px] min-w-0 flex-1 flex-col">
          <div
            className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-8"
            data-testid="chat-messages"
          >
            {messages.length === 0 && !send.isPending && (
              <div className="mx-auto mt-6 max-w-xl animate-fade-up">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-panel">
                  <Bot className="h-5 w-5 text-sky-400" />
                </div>
                <h2 className="text-lg font-semibold tracking-tight text-slate-100">
                  Ask anything about code
                </h2>
                <p className="mt-1 text-[13px] text-slate-500">
                  {ready
                    ? "Repository questions are answered with retrieved source evidence. General questions use programming knowledge only."
                    : "Ask general programming questions now - or upload a repository to get answers grounded in its source code."}
                </p>
                <div className="mt-5 grid gap-2 sm:grid-cols-2">
                  {(ready
                    ? [...REPO_EXAMPLES, ...GENERAL_EXAMPLES.slice(0, 2)]
                    : GENERAL_EXAMPLES
                  ).map((q) => (
                    <button
                      key={q}
                      type="button"
                      data-testid="suggestion-chip"
                      onClick={() => submit(q)}
                      className="rounded-lg border border-line bg-panel/40 px-3 py-2 text-left text-[12.5px] text-slate-300 transition-colors duration-150 hover:border-blue-500/50 hover:text-white"
                    >
                      {q}
                    </button>
                  ))}
                </div>
                {!repo && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-4"
                    onClick={openUpload}
                    data-testid="empty-upload-button"
                  >
                    <Upload className="h-3.5 w-3.5" /> Upload a repository
                  </Button>
                )}
              </div>
            )}
            <div className="mx-auto flex max-w-3xl flex-col gap-5">
              {messages.map((m) =>
                m.role === "user" ? (
                  <div
                    key={m.id}
                    className="flex justify-end"
                    data-testid="chat-user-message"
                  >
                    <div className="max-w-[80%] rounded-2xl rounded-br-md bg-blue-700 px-3.5 py-2 text-[14px] text-white">
                      {m.selection && (
                        <p className="mb-1 font-mono text-[11px] text-blue-200">
                          {m.selection.file_path} L{m.selection.start_line}-
                          {m.selection.end_line}
                        </p>
                      )}
                      {m.content}
                    </div>
                  </div>
                ) : (
                  <motion.div
                    key={m.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    data-testid="chat-assistant-message"
                    onClick={() => setActiveMsg(m.id)}
                    className={cn(
                      "rounded-xl border bg-[#131C2E]/70 px-4 py-3 transition-colors",
                      active?.id === m.id && m.evidence.length
                        ? "border-blue-500/30"
                        : "border-line",
                    )}
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      {m.scope && SCOPE_BADGE[m.scope] && (
                        <span
                          data-testid="message-scope-badge"
                          className={cn(
                            "rounded-full border px-2 py-0.5 text-[10.5px]",
                            SCOPE_BADGE[m.scope].cls,
                          )}
                        >
                          {SCOPE_BADGE[m.scope].label}
                        </span>
                      )}
                      {m.mode && (
                        <span className="text-[10.5px] capitalize text-slate-500">
                          {m.mode} mode
                        </span>
                      )}
                      {m.evidence.length > 0 && (
                        <button
                          type="button"
                          data-testid="view-evidence-button"
                          onClick={() => {
                            setActiveMsg(m.id);
                            setTab("evidence");
                          }}
                          className="ml-auto text-[11px] text-blue-400 hover:underline"
                        >
                          {m.evidence.length} evidence snippet
                          {m.evidence.length > 1 ? "s" : ""}
                        </button>
                      )}
                      {m.scope === "general" && (
                        <button
                          type="button"
                          data-testid="concept-alternatives-button"
                          onClick={() =>
                            setAltConcept(
                              messages[messages.indexOf(m) - 1]?.content ??
                                m.content.slice(0, 500),
                            )
                          }
                          className="ml-auto inline-flex items-center gap-1 text-[11px] text-violet-300 hover:underline"
                        >
                          <Wand2 className="h-3 w-3" />
                          Alternative implementations
                        </button>
                      )}
                    </div>
                    {m.confidence && m.scope === "repo" && (
                      <div className="mb-2 max-w-xs">
                        <ConfidenceMeter c={m.confidence} compact />
                      </div>
                    )}
                    <Markdown text={m.content} onCite={(id) => cite(m, id)} />
                  </motion.div>
                ),
              )}
              {send.isPending && (
                <>
                  <div className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-br-md bg-blue-700/70 px-3.5 py-2 text-[14px] text-white">
                      {send.variables}
                    </div>
                  </div>
                  <div
                    className="rounded-xl border border-line bg-[#131C2E]/70 px-4 py-3"
                    data-testid="chat-loading"
                  >
                    <p className="mb-2 flex items-center gap-2 text-[12px] text-slate-400">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      {ready && scope !== "general"
                        ? "Retrieving evidence and composing answer..."
                        : "Thinking..."}
                    </p>
                    <div className="space-y-1.5">
                      <div className="skeleton h-3 w-11/12" />
                      <div className="skeleton h-3 w-4/5" />
                      <div className="skeleton h-3 w-3/5" />
                    </div>
                  </div>
                </>
              )}
              <div ref={endRef} />
            </div>
          </div>

          <div className="border-t border-line bg-page px-4 py-3 md:px-8">
            <div className="mx-auto max-w-3xl">
              <AnimatePresence>
                {(selection || fileCtx) && ready && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="mb-2 flex flex-wrap gap-2"
                  >
                    {selection ? (
                      <span
                        data-testid="selection-indicator"
                        className="inline-flex items-center gap-1.5 rounded-md border border-violet-500/50 bg-violet-500/10 px-2 py-1 font-mono text-[11.5px] text-violet-200"
                      >
                        <MousePointerSquareDashed className="h-3.5 w-3.5" />
                        Selected: {selection.file_path} L{selection.start_line}-
                        {selection.end_line}
                        <button
                          type="button"
                          data-testid="clear-selection-button"
                          title="Clear selection"
                          onClick={() => setSelection(null)}
                          className="ml-1 text-violet-300 hover:text-white"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </span>
                    ) : (
                      fileCtx && (
                        <span
                          data-testid="file-context-indicator"
                          className="inline-flex items-center gap-1.5 rounded-md border border-sky-500/50 bg-sky-500/10 px-2 py-1 font-mono text-[11.5px] text-sky-200"
                        >
                          <FileCode2 className="h-3.5 w-3.5" />
                          Asking about {fileCtx}
                          <button
                            type="button"
                            data-testid="clear-file-context"
                            onClick={() => setFileCtx(null)}
                            className="ml-1 hover:text-white"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </span>
                      )
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
              <div className="flex items-end gap-2 rounded-xl border border-line bg-panel/60 p-2 transition-colors focus-within:border-blue-500/60">
                <textarea
                  ref={inputRef}
                  data-testid="chat-input"
                  rows={1}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      submit();
                    }
                  }}
                  placeholder={
                    selection
                      ? "Ask about the selected code - e.g. Explain this condition"
                      : ready
                        ? "Ask about the repository or any programming concept..."
                        : "Ask a programming question..."
                  }
                  className="max-h-40 min-h-[38px] flex-1 resize-none bg-transparent px-2 py-2 text-[14px] text-slate-100 outline-none placeholder:text-slate-600"
                />
                <Button
                  data-testid="chat-send-button"
                  size="icon"
                  disabled={!text.trim() || send.isPending}
                  onClick={() => submit()}
                >
                  {send.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <SendHorizontal className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="mt-1.5 text-[11px] text-slate-600">
                Enter to send · Shift+Enter for newline ·{" "}
                {repo && !ready
                  ? "repository is indexing - answers are general until ready"
                  : "AI can make mistakes - check the evidence"}
              </p>
            </div>
          </div>
        </section>

        <aside className="flex min-h-[480px] w-full flex-col border-t border-line bg-evidence lg:w-[44%] lg:max-w-[720px] lg:border-l lg:border-t-0">
          <div className="flex items-center gap-1 border-b border-line px-2 py-1.5">
            {(["evidence", "source"] as const).map((t) => (
              <button
                key={t}
                type="button"
                data-testid={`right-tab-${t}`}
                onClick={() => setTab(t)}
                className={cn(
                  "relative rounded-md px-3 py-1.5 text-[12.5px] capitalize transition-colors",
                  tab === t
                    ? "text-slate-100"
                    : "text-slate-500 hover:text-slate-300",
                )}
              >
                {tab === t && (
                  <motion.span
                    layoutId="right-tab"
                    className="absolute inset-0 rounded-md bg-slate-800"
                    transition={{ duration: 0.18 }}
                  />
                )}
                <span className="relative">
                  {t === "evidence"
                    ? `Evidence${active?.evidence.length ? ` (${active.evidence.length})` : ""}`
                    : "Source"}
                </span>
              </button>
            ))}
          </div>
          {tab === "evidence" ? (
            <EvidencePanel
              evidence={active?.evidence ?? []}
              confidence={active?.confidence ?? null}
              scope={active?.scope ?? null}
              onOpen={openEvidence}
            />
          ) : repo && ready ? (
            <SourcePanel
              repoId={repo.id}
              onAskFile={(p) => {
                setSelection(null);
                setFileCtx(p);
                inputRef.current?.focus();
              }}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center p-8 text-center text-[12.5px] text-slate-500">
              {repo
                ? "Source viewer is available once indexing finishes."
                : "Upload a repository to browse its source code."}
            </div>
          )}
        </aside>
      </div>
      <AlternativesDialog
        repoId={null}
        symbol={null}
        concept={altConcept ?? undefined}
        open={!!altConcept}
        onOpenChange={(o) => !o && setAltConcept(null)}
      />
    </div>
  );
}
