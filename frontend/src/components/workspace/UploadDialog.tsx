import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import {
  FileArchive,
  FileCode2,
  FlaskConical,
  Github,
  HelpCircle,
  Loader2,
  UploadCloud,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { apiPost, apiUpload } from "@/lib/api";
import { errMsg, useApp } from "@/lib/appState";
import type { RepoOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const GUIDE = [
  "Open the GitHub repository in your browser.",
  "Click the green Code button above the file list.",
  "Select Download ZIP.",
  "Extract the downloaded archive if your browser unpacked it - otherwise keep the .zip as is.",
  "Upload the ZIP file into CodeAtlas here.",
];

export function UploadDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const { setRepoId } = useApp();
  const qc = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [drag, setDrag] = useState(false);
  const [guide, setGuide] = useState(false);
  const [url, setUrl] = useState("");
  const input = useRef<HTMLInputElement>(null);

  const done = (repo: RepoOut) => {
    setRepoId(repo.id);
    void qc.invalidateQueries({ queryKey: ["repos"] });
    qc.setQueryData(["repo", repo.id], repo);
    toast.info(`Indexing ${repo.name}... progress is shown in the sidebar`);
    setFiles([]);
    setUrl("");
    onOpenChange(false);
  };
  const upload = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      files.forEach((f) =>
        fd.append(
          "files",
          f,
          (f as File & { webkitRelativePath?: string }).webkitRelativePath ||
            f.name,
        ),
      );
      return apiUpload<RepoOut>("/repos/upload", fd);
    },
    onSuccess: done,
    onError: (e) => toast.error(errMsg(e)),
  });
  const github = useMutation({
    mutationFn: () => apiPost<RepoOut>("/repos/github", { url }),
    onSuccess: done,
    onError: (e) => toast.error(errMsg(e)),
  });
  const sample = useMutation({
    mutationFn: () => apiPost<RepoOut>("/repos/sample"),
    onSuccess: done,
    onError: (e) => toast.error(errMsg(e)),
  });

  const addFiles = (list: FileList | null) =>
    list && setFiles((p) => [...p, ...Array.from(list)]);
  const busy = upload.isPending || github.isPending || sample.isPending;
  const hasZip = files.some((f) => f.name.toLowerCase().endsWith(".zip"));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl" data-testid="upload-dialog">
        <DialogHeader>
          <DialogTitle>Add a repository</DialogTitle>
          <DialogDescription>
            Upload a ZIP archive or source files, or import a public GitHub
            repository with its history.
          </DialogDescription>
        </DialogHeader>
        <div
          data-testid="upload-dropzone"
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            addFiles(e.dataTransfer.files);
          }}
          onClick={() => input.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-7 text-center transition-colors duration-150",
            drag
              ? "border-blue-400 bg-blue-500/10"
              : "border-slate-700 bg-editor hover:border-slate-500",
          )}
        >
          <UploadCloud className="h-7 w-7 text-blue-400" />
          <p className="text-[13.5px] text-slate-200">
            Drag & drop a .zip or source files, or{" "}
            <span className="text-blue-400">browse</span>
          </p>
          <p className="text-[11.5px] text-slate-500">
            ZIP up to 50 MB · files up to 400 KB · node_modules, .git, dist,
            build, vendor are skipped
          </p>
          <input
            ref={input}
            data-testid="upload-file-input"
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </div>
        {files.length > 0 && (
          <div className="scroll-thin max-h-32 space-y-1 overflow-y-auto">
            {files.map((f, i) => (
              <div
                key={i}
                className="flex items-center gap-2 rounded-md bg-panel px-2 py-1 text-[12.5px]"
              >
                {f.name.endsWith(".zip") ? (
                  <FileArchive className="h-3.5 w-3.5 text-amber-400" />
                ) : (
                  <FileCode2 className="h-3.5 w-3.5 text-sky-400" />
                )}
                <span className="flex-1 truncate">{f.name}</span>
                <span className="text-slate-500">
                  {(f.size / 1024).toFixed(1)} KB
                </span>
                <button
                  type="button"
                  onClick={() => setFiles((p) => p.filter((_, k) => k !== i))}
                  className="text-slate-500 hover:text-slate-200"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
        {hasZip && files.length > 1 && (
          <p className="text-[12px] text-amber-300">
            Upload a single ZIP, or source files - not both.
          </p>
        )}
        <Button
          data-testid="upload-submit-button"
          disabled={!files.length || busy || (hasZip && files.length > 1)}
          onClick={() => upload.mutate()}
        >
          {upload.isPending && <Loader2 className="h-4 w-4 animate-spin" />}{" "}
          Upload & index {files.length ? `(${files.length})` : ""}
        </Button>

        <button
          type="button"
          data-testid="github-guide-toggle"
          onClick={() => setGuide((g) => !g)}
          className="flex items-center gap-1.5 self-start text-[12.5px] text-blue-400 hover:text-blue-300"
        >
          <HelpCircle className="h-3.5 w-3.5" /> How do I get a GitHub
          repository?
        </button>
        <AnimatePresence>
          {guide && (
            <motion.ol
              data-testid="github-guide"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="space-y-1.5 overflow-hidden rounded-lg border border-line bg-panel/60 p-3 text-[12.5px] text-slate-300"
            >
              {GUIDE.map((g, i) => (
                <li key={i} className="flex gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-500/15 text-[11px] text-blue-300">
                    {i + 1}
                  </span>
                  {g}
                </li>
              ))}
            </motion.ol>
          )}
        </AnimatePresence>

        <div className="border-t border-line pt-3">
          <p className="mb-1.5 flex items-center gap-1.5 text-[12px] font-medium text-slate-400">
            <Github className="h-3.5 w-3.5" /> Or import a public GitHub URL
            (includes Git history)
          </p>
          <div className="flex gap-2">
            <Input
              data-testid="github-url-input"
              placeholder="https://github.com/owner/repo"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <Button
              data-testid="github-import-button"
              variant="secondary"
              disabled={!url.trim() || busy}
              onClick={() => github.mutate()}
            >
              {github.isPending && <Loader2 className="h-4 w-4 animate-spin" />}{" "}
              Import
            </Button>
          </div>
        </div>
        <button
          type="button"
          data-testid="load-sample-button"
          disabled={busy}
          onClick={() => sample.mutate()}
          className="flex items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-2 text-left text-[12.5px] text-amber-200 transition-colors hover:bg-amber-500/10"
        >
          <FlaskConical className="h-4 w-4" />
          <span>
            <b>Load the sample project</b> - a small labelled demo repo (Python
            auth service + JS form) to try every feature.
          </span>
        </button>
      </DialogContent>
    </Dialog>
  );
}
