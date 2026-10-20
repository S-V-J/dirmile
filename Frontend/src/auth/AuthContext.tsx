import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import * as api from "../api/client";
import type { LoginPayload, RegisterPayload, User } from "../types/api";

// ── Context shape ────────────────────────────────────────────────────

export interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;
}

export interface AuthContextValue extends AuthState {
  login: (payload: LoginPayload) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
  clearError: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ─────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    error: null,
  });

  const refreshUser = useCallback(async (): Promise<User | null> => {
    try {
      const user = await api.getCurrentUser();
      setState({ user, isLoading: false, error: null });
      return user;
    } catch (err) {
      if (err instanceof api.ApiRequestError && err.status === 401) {
        setState({ user: null, isLoading: false, error: null });
        return null;
      }
      setState({
        user: null,
        isLoading: false,
        error: err instanceof Error ? err.message : "Failed to load user.",
      });
      return null;
    }
  }, []);

  // On mount, try to restore session.
  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (payload: LoginPayload): Promise<User> => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const user = await api.login(payload);
      setState({ user, isLoading: false, error: null });
      return user;
    } catch (err) {
      const message =
        err instanceof api.ApiRequestError
          ? typeof err.data.detail === "string"
            ? err.data.detail
            : "Login failed."
          : "Login failed.";
      setState((prev) => ({ ...prev, isLoading: false, error: message }));
      throw err;
    }
  }, []);

  const register = useCallback(
    async (payload: RegisterPayload): Promise<User> => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const user = await api.register(payload);
        setState({ user, isLoading: false, error: null });
        return user;
      } catch (err) {
        const message =
          err instanceof api.ApiRequestError
            ? typeof err.data.detail === "string"
              ? err.data.detail
              : "Registration failed."
            : "Registration failed.";
        setState((prev) => ({ ...prev, isLoading: false, error: message }));
        throw err;
      }
    },
    [],
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await api.logout();
    } finally {
      setState({ user: null, isLoading: false, error: null });
    }
  }, []);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login,
      register,
      logout,
      refreshUser,
      clearError,
    }),
    [state, login, register, logout, refreshUser, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
