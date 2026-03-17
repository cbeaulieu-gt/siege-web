import { useEffect, useState } from "react";
import apiClient from "../api/client";

type HealthStatus = "loading" | "healthy" | "unreachable";

function HomePage() {
  const [status, setStatus] = useState<HealthStatus>("loading");

  useEffect(() => {
    apiClient
      .get<{ status: string }>("/api/health")
      .then(() => {
        setStatus("healthy");
      })
      .catch(() => {
        setStatus("unreachable");
      });
  }, []);

  const statusLabel: Record<HealthStatus, string> = {
    loading: "API: checking...",
    healthy: "API: healthy",
    unreachable: "API: unreachable",
  };

  const statusColor: Record<HealthStatus, string> = {
    loading: "text-gray-500",
    healthy: "text-green-600",
    unreachable: "text-red-600",
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50">
      <div className="rounded-xl bg-white p-10 shadow-md">
        <h1 className="mb-6 text-3xl font-bold text-gray-900">
          Siege Assignment System
        </h1>
        <p className={`text-lg font-medium ${statusColor[status]}`}>
          {statusLabel[status]}
        </p>
      </div>
    </div>
  );
}

export default HomePage;
