import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Boxes, GitBranch, Loader2, Network, Search } from "lucide-react";
import { toast } from "sonner";
import { apiPost } from "@/lib/api";
import { beginSession } from "@/lib/session";
import { errMsg, useMe } from "@/lib/appState";
import type { UserOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Login() {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const submit = useMutation({
    mutationFn: () =>
      apiPost<UserOut>(
        tab === "login" ? "/auth/login" : "/auth/register",
        tab === "login" ? { email, password } : { email, password, name },
      ),
    onSuccess: (u) => {
      beginSession();
      qc.setQueryData(["me"], u);
      toast.success(`Welcome${tab === "register" ? "" : " back"}, ${u.name}`);
      nav("/");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  if (me) return <Navigate to="/" replace />;
  return (
    <div className="flex min-h-screen bg-page text-slate-200">
      <div className="relative hidden flex-1 flex-col justify-between overflow-hidden border-r border-line bg-rail p-10 lg:flex">
        <div className="pointer-events-none absolute -left-40 -top-40 h-[480px] w-[480px] rounded-full bg-blue-600/10 blur-3xl" />
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-violet-600">
            <Boxes className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-semibold tracking-tight">
            CodeAtlas
          </span>
        </div>
        <div className="relative max-w-lg">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight text-slate-100">
            Understand any codebase.
            <br />
            <span className="text-slate-400">
              Explore how it works. Learn by interacting with it.
            </span>
          </h1>
          <div className="mt-8 space-y-3 font-mono text-[12.5px]">
            {[
              {
                icon: Search,
                t: 'hybrid_search("where is auth?")',
                s: "-> auth/login.py L28-39  evidence: high",
              },
              {
                icon: Network,
                t: "login() -> validate_credentials()",
                s: "-> get_user() -> database_query()",
              },
              {
                icon: GitBranch,
                t: "git log -L login",
                s: "-> real commits, real diffs",
              },
            ].map((r, i) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded-lg border border-line bg-editor/80 px-3 py-2.5"
              >
                <r.icon className="mt-0.5 h-4 w-4 text-sky-400" />
                <div>
                  <p className="text-slate-200">{r.t}</p>
                  <p className="text-slate-500">{r.s}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <p className="text-[12px] text-slate-600">
          Evidence-backed explanations · interactive code graphs · repository
          quizzes
        </p>
      </div>
      <div className="flex flex-1 items-center justify-center p-6">
        <form
          className="w-full max-w-sm space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            submit.mutate();
          }}
          data-testid="auth-form"
        >
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-slate-100">
              {tab === "login" ? "Sign in to CodeAtlas" : "Create your account"}
            </h2>
            <p className="mt-1 text-[13px] text-slate-500">
              Your repositories, conversations and quiz progress are saved to
              your account.
            </p>
          </div>
          <div className="grid grid-cols-2 rounded-lg border border-line bg-editor p-0.5 text-[13px]">
            {(["login", "register"] as const).map((t) => (
              <button
                key={t}
                type="button"
                data-testid={`auth-tab-${t}`}
                onClick={() => setTab(t)}
                className={cn(
                  "rounded-md py-1.5 transition-colors",
                  tab === t
                    ? "bg-slate-800 text-slate-100"
                    : "text-slate-500 hover:text-slate-300",
                )}
              >
                {t === "login" ? "Sign in" : "Sign up"}
              </button>
            ))}
          </div>
          {tab === "register" && (
            <div className="space-y-1.5">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                data-testid="auth-name-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              data-testid="auth-email-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pw">Password</Label>
            <Input
              id="pw"
              type="password"
              data-testid="auth-password-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>
          <Button
            type="submit"
            className="w-full"
            data-testid="auth-submit-button"
            disabled={submit.isPending}
          >
            {submit.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {tab === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
      </div>
    </div>
  );
}
