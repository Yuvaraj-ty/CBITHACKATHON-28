import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  FolderGit2,
  Loader2,
  RotateCcw,
  Sparkles,
  Target,
  Trophy,
  X,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";
import { errMsg, useApp, useCurrentRepo } from "@/lib/appState";
import type { AnswerOut, QuizOut, QuizResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CodeBlock } from "@/components/CodeBlock";

const TOPICS = [
  "Programming fundamentals",
  "Variables and data types",
  "Loops and conditions",
  "Functions",
  "Object-oriented programming",
  "Data structures",
  "Algorithms",
  "Python specifics",
  "JavaScript specifics",
  "Code output prediction",
];
const TYPE_LABEL: Record<string, string> = {
  multiple_choice: "Multiple choice",
  true_false: "True or false",
  predict_output: "Predict the output",
  identify_function: "Identify the function",
  code_understanding: "Understand the code",
  order_steps: "Arrange the steps",
};
const DIFFS = ["easy", "medium", "hard"] as const;

export default function Learning() {
  const { repoId } = useApp();
  const { data: repo } = useCurrentRepo();
  const ready = repo?.status === "ready";
  const qc = useQueryClient();
  const [kind, setKind] = useState<"general" | "repo">("general");
  const [topic, setTopic] = useState(TOPICS[0]);
  const [focus, setFocus] = useState("");
  const [difficulty, setDifficulty] =
    useState<(typeof DIFFS)[number]>("medium");
  const [count, setCount] = useState(5);
  const [quiz, setQuiz] = useState<QuizOut | null>(null);
  const [result, setResult] = useState<QuizResult | null>(null);
  const history = useQuery({
    queryKey: ["quiz-history"],
    queryFn: () => apiGet<QuizResult[]>("/quiz-history"),
  });

  const gen = useMutation({
    mutationFn: () =>
      apiPost<QuizOut>("/quiz/generate", {
        kind,
        topic,
        difficulty,
        count,
        repo_id: kind === "repo" ? repoId : null,
        focus: kind === "repo" ? focus || null : null,
      }),
    onSuccess: (q) => {
      setQuiz(q);
      setResult(null);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const stats = history.data ?? [];
  const avg = stats.length
    ? Math.round(stats.reduce((a, r) => a + r.percentage, 0) / stats.length)
    : 0;

  if (quiz && !result)
    return (
      <QuizRunner
        quiz={quiz}
        onExit={() => setQuiz(null)}
        onDone={(r) => {
          setResult(r);
          void qc.invalidateQueries({ queryKey: ["quiz-history"] });
        }}
      />
    );
  if (result)
    return (
      <Results
        r={result}
        onRetake={() => {
          setResult(null);
          setQuiz(null);
          gen.mutate();
        }}
        onBack={() => {
          setResult(null);
          setQuiz(null);
        }}
      />
    );

  return (
    <div className="scroll-thin flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6 md:p-8">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Learning
          </p>
          <h1 className="mt-0.5 text-2xl font-semibold tracking-tight text-slate-100">
            Test what you understand
          </h1>
          <p className="mt-1 text-[13px] text-slate-500">
            General programming quizzes or quizzes generated from the code in
            your repository - with explanations after every answer.
          </p>
        </div>
        <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
          <div
            className="rounded-xl border border-line bg-panel/50 p-5"
            data-testid="quiz-setup"
          >
            <div className="grid grid-cols-2 gap-2">
              {(
                [
                  ["general", "General programming", BookOpen, "Pick a topic"],
                  [
                    "repo",
                    "Repository quiz",
                    FolderGit2,
                    ready ? repo!.name : "Load a repository first",
                  ],
                ] as const
              ).map(([k, l, I, sub]) => (
                <button
                  key={k}
                  type="button"
                  data-testid={`quiz-kind-${k}`}
                  disabled={k === "repo" && !ready}
                  onClick={() => setKind(k)}
                  className={cn(
                    "rounded-lg border p-3 text-left transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40",
                    kind === k
                      ? "border-blue-500/60 bg-blue-500/10"
                      : "border-line hover:border-slate-600",
                  )}
                >
                  <I
                    className={cn(
                      "h-4 w-4",
                      kind === k ? "text-sky-300" : "text-slate-500",
                    )}
                  />
                  <p className="mt-2 text-[13.5px] font-medium text-slate-100">
                    {l}
                  </p>
                  <p className="truncate text-[11.5px] text-slate-500">{sub}</p>
                </button>
              ))}
            </div>
            <div className="mt-5">
              {kind === "general" ? (
                <>
                  <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                    Topic
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {TOPICS.map((t) => (
                      <button
                        key={t}
                        type="button"
                        data-testid={`quiz-topic-${t.toLowerCase().replace(/\s+/g, "-")}`}
                        onClick={() => setTopic(t)}
                        className={cn(
                          "rounded-full border px-3 py-1 text-[12px] transition-colors",
                          topic === t
                            ? "border-sky-400/60 bg-sky-500/15 text-sky-200"
                            : "border-line text-slate-400 hover:text-slate-200",
                        )}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                    Focus area (optional)
                  </p>
                  <Input
                    data-testid="quiz-focus-input"
                    value={focus}
                    onChange={(e) => setFocus(e.target.value)}
                    placeholder="e.g. authentication, database layer - blank = whole repository"
                  />
                  <p className="mt-1.5 text-[11.5px] text-slate-500">
                    Questions are generated only from retrieved code in{" "}
                    {repo?.name}; answers cite file paths and line numbers.
                  </p>
                </>
              )}
            </div>
            <div className="mt-5 flex flex-wrap items-end gap-6">
              <div>
                <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  Difficulty
                </p>
                <div className="inline-flex rounded-lg border border-line bg-editor p-0.5">
                  {DIFFS.map((d) => (
                    <button
                      key={d}
                      type="button"
                      data-testid={`quiz-difficulty-${d}`}
                      onClick={() => setDifficulty(d)}
                      className={cn(
                        "rounded-md px-3 py-1 text-[12.5px] capitalize transition-colors",
                        difficulty === d
                          ? "bg-slate-800 text-slate-100"
                          : "text-slate-500 hover:text-slate-300",
                      )}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  Questions
                </p>
                <div className="inline-flex rounded-lg border border-line bg-editor p-0.5">
                  {[3, 5, 10].map((n) => (
                    <button
                      key={n}
                      type="button"
                      data-testid={`quiz-count-${n}`}
                      onClick={() => setCount(n)}
                      className={cn(
                        "rounded-md px-3 py-1 text-[12.5px] transition-colors",
                        count === n
                          ? "bg-slate-800 text-slate-100"
                          : "text-slate-500 hover:text-slate-300",
                      )}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
              <Button
                data-testid="start-quiz-button"
                className="ml-auto"
                disabled={gen.isPending || (kind === "repo" && !ready)}
                onClick={() => gen.mutate()}
              >
                {gen.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                {gen.isPending ? "Generating quiz..." : "Start quiz"}
              </Button>
            </div>
            {gen.isPending && (
              <p className="mt-3 text-[12px] text-slate-500">
                Writing {count} questions
                {kind === "repo" ? " from your repository's code" : ""} - this
                can take up to a minute.
              </p>
            )}
          </div>

          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-3 gap-3">
              {[
                ["Quizzes", String(stats.length), Trophy],
                ["Average", stats.length ? `${avg}%` : "-", Target],
                [
                  "Best",
                  stats.length
                    ? `${Math.max(...stats.map((s) => s.percentage))}%`
                    : "-",
                  CheckCircle2,
                ],
              ].map(([l, v, I]) => {
                const Icon = I as typeof Trophy;
                return (
                  <div
                    key={l as string}
                    className="rounded-xl border border-line bg-panel/40 p-3"
                    data-testid={`stat-${(l as string).toLowerCase()}`}
                  >
                    <Icon className="h-4 w-4 text-slate-500" />
                    <p className="mt-2 text-xl font-semibold text-slate-100">
                      {v as string}
                    </p>
                    <p className="text-[11.5px] text-slate-500">
                      {l as string}
                    </p>
                  </div>
                );
              })}
            </div>
            <div
              className="rounded-xl border border-line bg-panel/40"
              data-testid="quiz-history"
            >
              <p className="border-b border-line px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                Quiz history
              </p>
              {history.isLoading && (
                <div className="space-y-2 p-4">
                  <div className="skeleton h-4" />
                  <div className="skeleton h-4" />
                </div>
              )}
              {stats.length === 0 && !history.isLoading && (
                <p className="p-4 text-[12.5px] text-slate-500">
                  No quizzes yet - your progress will be saved here.
                </p>
              )}
              <div className="scroll-thin max-h-80 overflow-y-auto">
                {stats.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setResult(r)}
                    className="flex w-full items-center gap-3 border-b border-line/60 px-4 py-2.5 text-left transition-colors last:border-0 hover:bg-slate-800/40"
                    data-testid="quiz-history-row"
                  >
                    <div
                      className={cn(
                        "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg font-mono text-[12px]",
                        r.percentage >= 70
                          ? "bg-emerald-500/15 text-emerald-300"
                          : r.percentage >= 40
                            ? "bg-amber-500/15 text-amber-300"
                            : "bg-red-500/15 text-red-300",
                      )}
                    >
                      {r.percentage}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] text-slate-200">
                        {r.kind === "repo"
                          ? `${r.repo_name} · ${r.topic}`
                          : r.topic}
                      </p>
                      <p className="text-[11px] capitalize text-slate-500">
                        {r.difficulty} · {r.score}/{r.total} ·{" "}
                        {r.completed_at?.slice(0, 10)}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function QuizRunner({
  quiz,
  onExit,
  onDone,
}: {
  quiz: QuizOut;
  onExit: () => void;
  onDone: (r: QuizResult) => void;
}) {
  const { openFile } = useApp();
  const nav = useNavigate();
  const [i, setI] = useState(0);
  const [choice, setChoice] = useState<number | null>(null);
  const [order, setOrder] = useState<number[]>([]);
  const [fb, setFb] = useState<AnswerOut | null>(null);
  const q = quiz.questions[i];
  const isOrder = q.type === "order_steps";
  const answer = useMutation({
    mutationFn: () =>
      apiPost<AnswerOut>(
        `/quiz/${quiz.id}/answer`,
        isOrder ? { index: i, order } : { index: i, choice },
      ),
    onSuccess: setFb,
    onError: (e) => toast.error(errMsg(e)),
  });
  const finish = useMutation({
    mutationFn: () => apiPost<QuizResult>(`/quiz/${quiz.id}/finish`),
    onSuccess: onDone,
    onError: (e) => toast.error(errMsg(e)),
  });
  const canSubmit = isOrder
    ? order.length === q.options.length
    : choice !== null;
  const last = i === quiz.questions.length - 1;
  const next = () => {
    if (last) finish.mutate();
    else {
      setI(i + 1);
      setChoice(null);
      setOrder([]);
      setFb(null);
    }
  };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === "INPUT") return;
      const n = Number(e.key);
      if (!fb && !isOrder && n >= 1 && n <= q.options.length) setChoice(n - 1);
      if (e.key === "Enter") {
        if (fb) next();
        else if (canSubmit) answer.mutate();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  return (
    <div className="scroll-thin flex-1 overflow-y-auto">
      <div
        className="mx-auto flex max-w-3xl flex-col gap-5 p-6 md:p-8"
        data-testid="quiz-runner"
      >
        <div className="flex items-center gap-3">
          <button
            type="button"
            data-testid="quiz-exit-button"
            onClick={onExit}
            className="text-slate-500 hover:text-slate-200"
            title="Leave quiz"
          >
            <X className="h-4 w-4" />
          </button>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-blue-500 to-violet-500"
              animate={{
                width: `${((i + (fb ? 1 : 0)) / quiz.questions.length) * 100}%`,
              }}
            />
          </div>
          <span
            data-testid="quiz-progress"
            className="font-mono text-[12px] text-slate-400"
          >
            {i + 1}/{quiz.questions.length}
          </span>
        </div>
        <AnimatePresence mode="wait">
          <motion.div
            key={i}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12 }}
            transition={{ duration: 0.18 }}
            className="space-y-4"
          >
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span
                className="rounded-full border border-blue-500/40 px-2 py-0.5 text-blue-300"
                data-testid="quiz-question-type"
              >
                {TYPE_LABEL[q.type] ?? q.type}
              </span>
              <span className="rounded-full border border-line px-2 py-0.5 text-slate-400">
                {q.topic}
              </span>
              <span className="rounded-full border border-line px-2 py-0.5 capitalize text-slate-400">
                {quiz.difficulty}
              </span>
              {quiz.repo_name && (
                <span className="rounded-full border border-line px-2 py-0.5 text-slate-400">
                  {quiz.repo_name}
                </span>
              )}
            </div>
            <h2
              data-testid="quiz-question-text"
              className="text-[17px] font-medium leading-snug text-slate-100"
            >
              {q.question}
            </h2>
            {q.code && (
              <CodeBlock
                code={q.code}
                language={q.language}
                className="max-h-80"
              />
            )}
            {isOrder ? (
              <div className="space-y-2">
                <p className="text-[12px] text-slate-500">
                  Click the steps in the order they execute.
                </p>
                {q.options.map((o, k) => {
                  const pos = order.indexOf(k);
                  return (
                    <button
                      key={k}
                      type="button"
                      disabled={!!fb}
                      data-testid={`quiz-option-${k}`}
                      onClick={() =>
                        setOrder((p) =>
                          p.includes(k) ? p.filter((x) => x !== k) : [...p, k],
                        )
                      }
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-[13.5px] transition-colors",
                        pos >= 0
                          ? "border-violet-500/60 bg-violet-500/10"
                          : "border-line hover:border-slate-600",
                      )}
                    >
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-800 font-mono text-[11px] text-slate-300">
                        {pos >= 0 ? pos + 1 : "·"}
                      </span>
                      {o}
                    </button>
                  );
                })}
                {order.length > 0 && !fb && (
                  <button
                    type="button"
                    onClick={() => setOrder([])}
                    className="text-[12px] text-slate-500 hover:text-slate-300"
                  >
                    <RotateCcw className="mr-1 inline h-3 w-3" />
                    Reset order
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {q.options.map((o, k) => {
                  const isCorrect = fb && o === fb.correct_answer;
                  const isWrongPick = fb && choice === k && !fb.correct;
                  return (
                    <button
                      key={k}
                      type="button"
                      disabled={!!fb}
                      data-testid={`quiz-option-${k}`}
                      onClick={() => setChoice(k)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-[13.5px] transition-colors duration-150",
                        isCorrect
                          ? "border-emerald-500/70 bg-emerald-500/10"
                          : isWrongPick
                            ? "border-red-500/70 bg-red-500/10"
                            : choice === k
                              ? "border-blue-500/70 bg-blue-500/10"
                              : "border-line hover:border-slate-600",
                      )}
                    >
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-800 font-mono text-[11px] text-slate-300">
                        {String.fromCharCode(65 + k)}
                      </span>
                      <span className="flex-1">{o}</span>
                      {isCorrect && (
                        <Check className="h-4 w-4 text-emerald-400" />
                      )}
                      {isWrongPick && <X className="h-4 w-4 text-red-400" />}
                    </button>
                  );
                })}
              </div>
            )}
            {fb && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                data-testid="quiz-feedback"
                className={cn(
                  "space-y-2.5 rounded-xl border p-4",
                  fb.correct
                    ? "border-emerald-500/40 bg-emerald-500/5"
                    : "border-orange-500/40 bg-orange-500/5",
                )}
              >
                <p
                  className={cn(
                    "flex items-center gap-2 text-[14px] font-medium",
                    fb.correct ? "text-emerald-300" : "text-orange-300",
                  )}
                  data-testid="quiz-feedback-result"
                >
                  {fb.correct ? (
                    <CheckCircle2 className="h-4.5 w-4.5" />
                  ) : (
                    <XCircle className="h-4.5 w-4.5" />
                  )}
                  {fb.correct
                    ? "Correct - nice work!"
                    : "Not quite - here's why"}
                </p>
                {!fb.correct && (
                  <p className="text-[13px] text-slate-300">
                    <span className="text-slate-500">Correct answer: </span>
                    {fb.correct_answer}
                  </p>
                )}
                <p className="text-[13px] leading-relaxed text-slate-300">
                  {fb.explanation}
                </p>
                {fb.why_others_wrong && (
                  <p className="text-[12.5px] leading-relaxed text-slate-400">
                    <span className="text-slate-500">
                      Why the other options are wrong:{" "}
                    </span>
                    {fb.why_others_wrong}
                  </p>
                )}
                {fb.reference && (
                  <div data-testid="quiz-reference">
                    <div className="mb-1 flex items-center gap-2">
                      <p className="font-mono text-[11.5px] text-sky-300">
                        {fb.reference.file_path} · lines{" "}
                        {fb.reference.start_line}-{fb.reference.end_line}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          openFile(
                            fb.reference!.file_path,
                            fb.reference!.start_line,
                            fb.reference!.end_line,
                          );
                          nav("/");
                        }}
                        className="text-[11px] text-blue-400 hover:underline"
                      >
                        Open in Workspace
                      </button>
                    </div>
                    <CodeBlock
                      code={fb.reference.code}
                      language={fb.reference.language}
                      startLine={fb.reference.start_line}
                      className="max-h-56"
                    />
                  </div>
                )}
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>
        <div className="flex justify-end gap-2">
          {!fb ? (
            <Button
              data-testid="quiz-submit-button"
              disabled={!canSubmit || answer.isPending}
              onClick={() => answer.mutate()}
            >
              {answer.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Submit answer
            </Button>
          ) : (
            <Button
              data-testid="quiz-next-button"
              disabled={finish.isPending}
              onClick={next}
            >
              {finish.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              {last ? "See results" : "Next question"}
              <ArrowRight className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function Results({
  r,
  onRetake,
  onBack,
}: {
  r: QuizResult;
  onRetake: () => void;
  onBack: () => void;
}) {
  const circ = 2 * Math.PI * 52;
  return (
    <div className="scroll-thin flex-1 overflow-y-auto">
      <div
        className="mx-auto flex max-w-3xl flex-col gap-6 p-6 md:p-8"
        data-testid="quiz-results"
      >
        <div className="flex flex-wrap items-center gap-6 rounded-xl border border-line bg-panel/50 p-6">
          <svg width="128" height="128" className="-rotate-90">
            <circle
              cx="64"
              cy="64"
              r="52"
              stroke="#1E293B"
              strokeWidth="10"
              fill="none"
            />
            <motion.circle
              cx="64"
              cy="64"
              r="52"
              stroke={
                r.percentage >= 70
                  ? "#10B981"
                  : r.percentage >= 40
                    ? "#F59E0B"
                    : "#EF4444"
              }
              strokeWidth="10"
              fill="none"
              strokeLinecap="round"
              strokeDasharray={circ}
              initial={{ strokeDashoffset: circ }}
              animate={{ strokeDashoffset: circ * (1 - r.percentage / 100) }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            />
          </svg>
          <div>
            <p
              className="text-4xl font-semibold text-slate-100"
              data-testid="quiz-result-percentage"
            >
              {r.percentage}%
            </p>
            <p
              className="text-[13px] text-slate-400"
              data-testid="quiz-result-score"
            >
              {r.score} correct · {r.total - r.score} incorrect · {r.total}{" "}
              questions
            </p>
            <p className="mt-2 text-[14px] text-slate-200">{r.message}</p>
            <p className="text-[12px] capitalize text-slate-500">
              {r.kind === "repo" ? `${r.repo_name} · ` : ""}
              {r.topic} · {r.difficulty}
            </p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-4">
            <p className="mb-2 text-[12px] font-medium text-emerald-300">
              Understood well
            </p>
            {r.strong.length ? (
              r.strong.map((t) => (
                <span
                  key={t}
                  className="mb-1 mr-1 inline-block rounded-full bg-emerald-500/15 px-2 py-0.5 text-[12px] text-emerald-200"
                >
                  {t}
                </span>
              ))
            ) : (
              <p className="text-[12px] text-slate-500">
                Keep going - strengths will show here.
              </p>
            )}
          </div>
          <div className="rounded-xl border border-orange-500/25 bg-orange-500/5 p-4">
            <p className="mb-2 text-[12px] font-medium text-orange-300">
              Worth revisiting
            </p>
            {r.weak.length ? (
              r.weak.map((t) => (
                <span
                  key={t}
                  className="mb-1 mr-1 inline-block rounded-full bg-orange-500/15 px-2 py-0.5 text-[12px] text-orange-200"
                >
                  {t}
                </span>
              ))
            ) : (
              <p className="text-[12px] text-slate-500">
                Nothing major - well done.
              </p>
            )}
          </div>
        </div>
        <div className="rounded-xl border border-line bg-panel/40 p-4">
          <p className="mb-2 text-[12px] font-medium text-slate-300">
            Topic breakdown
          </p>
          {r.topics.map((t) => (
            <div
              key={t.topic}
              className="mb-2 flex items-center gap-3 text-[12px]"
            >
              <span className="w-44 truncate text-slate-400">{t.topic}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full bg-blue-500"
                  style={{ width: `${(t.correct / t.total) * 100}%` }}
                />
              </div>
              <span className="font-mono text-slate-500">
                {t.correct}/{t.total}
              </span>
            </div>
          ))}
        </div>
        <div
          className="rounded-xl border border-line bg-panel/40 p-4"
          data-testid="quiz-recommendations"
        >
          <p className="mb-2 text-[12px] font-medium text-slate-300">
            Explore next
          </p>
          <ul className="space-y-1 text-[12.5px] text-slate-400">
            {r.recommendations.map((x, i) => (
              <li key={i} className="flex gap-2">
                <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-blue-400" />
                {x}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex gap-2">
          <Button data-testid="quiz-retake-button" onClick={onRetake}>
            <RotateCcw className="h-4 w-4" />
            New quiz, same settings
          </Button>
          <Button
            variant="outline"
            data-testid="quiz-back-button"
            onClick={onBack}
          >
            Back to dashboard
          </Button>
        </div>
      </div>
    </div>
  );
}
