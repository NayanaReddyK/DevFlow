
import api from "./axios";
import type { User, AuthTokens } from "../types/user";

export const loginUser = async (
  email: string,
  password: string
): Promise<AuthTokens> => {
  const response = await api.post<AuthTokens>("/auth/login/", {
    email,
    password,
  });

  return response.data;
};

export const getCurrentUser = async (): Promise<User> => {
  const response = await api.get<User>("/auth/me/");
  return response.data;
};

export const refreshAccessToken = async (
  refresh: string
): Promise<{ access: string }> => {
  const response = await api.post("/auth/token/refresh/", {
    refresh,
  });

  return response.data;
};

export const logoutUser = async (refresh: string): Promise<void> => {
  await api.post("/auth/logout/", {
    refresh,
  });
};
