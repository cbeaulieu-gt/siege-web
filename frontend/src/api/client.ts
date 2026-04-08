import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !window.location.pathname.startsWith("/login") &&
      !error.config?.url?.includes("/api/auth/me")
    ) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default apiClient;
