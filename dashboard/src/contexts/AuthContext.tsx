import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { UserResponse } from "@/types";
import { authService } from "@/services/authService";

interface AuthContextType {
  user: UserResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName: string,
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("forgeline_token"),
  );
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setIsLoading(false);
      return;
    }

    authService
      .getMe()
      .then((u) => {
        setUser(u);
      })
      .catch(() => {
        localStorage.removeItem("forgeline_token");
        localStorage.removeItem("forgeline_user");
        setToken(null);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, [token]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authService.login({ email, password });
    localStorage.setItem("forgeline_token", res.token.access_token);
    localStorage.setItem("forgeline_user", JSON.stringify(res.user));
    setToken(res.token.access_token);
    setUser(res.user);
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      const res = await authService.register({
        email,
        password,
        full_name: fullName,
      });
      localStorage.setItem("forgeline_token", res.token.access_token);
      localStorage.setItem("forgeline_user", JSON.stringify(res.user));
      setToken(res.token.access_token);
      setUser(res.user);
    },
    [],
  );

  const logout = useCallback(() => {
    localStorage.removeItem("forgeline_token");
    localStorage.removeItem("forgeline_user");
    localStorage.removeItem("forgeline_project_id");
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
