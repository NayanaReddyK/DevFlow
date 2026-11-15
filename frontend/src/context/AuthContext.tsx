
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import type { User } from "../types/user";
import {
  loginUser,
  getCurrentUser,
  logoutUser,
} from "../api/authApi";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initializeAuth = async () => {
      const access = sessionStorage.getItem("access_token");

      if (!access) {
        setLoading(false);
        return;
      }

      try {
        const currentUser = await getCurrentUser();
        setUser(currentUser);
      } catch {
        sessionStorage.removeItem("access_token");
        sessionStorage.removeItem("refresh_token");
      } finally {
        setLoading(false);
      }
    };

    initializeAuth();
  }, []);

  const login = async (email: string, password: string) => {
    const tokens = await loginUser(email, password);

    sessionStorage.setItem("access_token", tokens.access);
    sessionStorage.setItem("refresh_token", tokens.refresh);

    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      sessionStorage.removeItem("access_token");
      sessionStorage.removeItem("refresh_token");
      throw error;
    }
  };

  const logout = async () => {
    const refresh = sessionStorage.getItem("refresh_token");

    try {
      if (refresh) {
        await logoutUser(refresh);
      }
    } finally {
      sessionStorage.removeItem("access_token");
      sessionStorage.removeItem("refresh_token");
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return context;
}
