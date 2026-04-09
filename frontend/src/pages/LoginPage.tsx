import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import apiClient from "../api/client";
import { Shield } from "lucide-react";

const ERROR_MESSAGES: Record<string, string> = {
  service_unavailable:
    "Login is temporarily unavailable. Please try again in a moment.",
};
const DEFAULT_ERROR = "You are not authorized to access this app.";

export default function LoginPage() {
  const [searchParams] = useSearchParams();
  const error = searchParams.get("error");
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async () => {
    setIsLoading(true);
    try {
      const { data } = await apiClient.get("/api/auth/login");
      window.location.href = data.url;
    } catch {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="w-full max-w-sm space-y-6 rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex flex-col items-center gap-2">
          <Shield className="h-8 w-8 text-violet-600" />
          <h1 className="text-xl font-semibold text-slate-900">
            Siege Assignments
          </h1>
        </div>
        {error && (
          <div className="rounded-md bg-red-50 p-3 text-center text-sm text-red-700">
            {ERROR_MESSAGES[error] ?? DEFAULT_ERROR}
          </div>
        )}
        <div className="space-y-4">
          <button
            onClick={handleLogin}
            disabled={isLoading}
            className="flex w-full items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium text-white transition-colors disabled:opacity-50"
            style={{ backgroundColor: "#5865F2" }}
          >
            {isLoading ? "Signing in..." : "Sign in with Discord"}
          </button>
          <p className="text-center text-xs text-slate-500">
            We only request access to your Discord username and avatar. Guild
            membership is verified privately using our bot.
          </p>
        </div>
      </div>
    </div>
  );
}
