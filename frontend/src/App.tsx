import { Navigate, Route, Routes } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { AppStateProvider, useMe } from "@/lib/appState";
import { AppShell } from "@/components/layout/AppShell";
import { Toaster } from "@/components/ui/sonner";
import Login from "@/pages/Login";
import Workspace from "@/pages/Workspace";
import Explorer from "@/pages/Explorer";
import Learning from "@/pages/Learning";

function Protected() {
  const { data, isLoading, isError } = useMe();
  if (isLoading)
    return (
      <div className="flex h-screen items-center justify-center bg-page text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  if (isError || !data) return <Navigate to="/login" replace />;
  return <AppShell />;
}

export default function App() {
  return (
    <AppStateProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Protected />}>
          <Route path="/" element={<Workspace />} />
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/learn" element={<Learning />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster richColors />
    </AppStateProvider>
  );
}
