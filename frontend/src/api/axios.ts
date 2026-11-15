
import axios, {
  type AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

interface RetryRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

// Attach the access token to outgoing requests.
api.interceptors.request.use((config) => {
  const accessToken = sessionStorage.getItem("access_token");

  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  return config;
});

// Refresh the access token when the backend returns 401.
let refreshPromise: Promise<string> | null = null;

api.interceptors.response.use(
  (response) => response,

  async (error: AxiosError) => {
    const originalRequest = error.config as
      | RetryRequestConfig
      | undefined;

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      originalRequest.url?.includes("/auth/login/") ||
      originalRequest.url?.includes("/auth/token/refresh/") ||
      originalRequest.url?.includes("/auth/logout/")
    ) {
      return Promise.reject(error);
    }

    const refreshToken = sessionStorage.getItem("refresh_token");

    if (!refreshToken) {
      sessionStorage.removeItem("access_token");
      sessionStorage.removeItem("refresh_token");
      window.location.assign("/login");
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      if (!refreshPromise) {
        refreshPromise = axios
          .post<{ access: string; refresh?: string }>(
            `${API_BASE_URL}/auth/token/refresh/`,
            { refresh: refreshToken }
          )
          .then((response) => {
            sessionStorage.setItem(
              "access_token",
              response.data.access
            );

            // SimpleJWT may return a new refresh token when rotation
            // is enabled. Store it if the backend provides one.
            if (response.data.refresh) {
              sessionStorage.setItem(
                "refresh_token",
                response.data.refresh
              );
            }

            return response.data.access;
          })
          .finally(() => {
            refreshPromise = null;
          });
      }

      const newAccessToken = await refreshPromise;

      originalRequest.headers.Authorization =
        `Bearer ${newAccessToken}`;

      return api(originalRequest);
    } catch (refreshError) {
      sessionStorage.removeItem("access_token");
      sessionStorage.removeItem("refresh_token");

      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }

      return Promise.reject(refreshError);
    }
  }
);

export default api;
