import { createContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, setAuthToken, setUnauthorizedHandler } from "../services/api";
import type { User } from "../types";

export interface AuthContextType {
  user: User | null;
  token: string | null;
  needsBootstrap: boolean;
  loading: boolean;
  login: (name: string, pin: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrapOwner: (name: string, pin: string) => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [needsBootstrap, setNeedsBootstrap] = useState(false);
  const [loading, setLoading] = useState(true);

  // Initialize auth state on mount
  useEffect(() => {
    const init = async () => {
      try {
        // Try to restore session from localStorage
        const storedToken = localStorage.getItem("pos_token");
        if (storedToken) {
          setAuthToken(storedToken);
          setToken(storedToken);
          try {
            const currentUser = await api.getMe();
            setUser(currentUser);
          } catch {
            // Token is invalid, clear it
            localStorage.removeItem("pos_token");
            setAuthToken(null);
            setToken(null);
            setUser(null);
          }
        } else {
          // No token: check bootstrap status
          try {
            const status = await api.getBootstrapStatus();
            setNeedsBootstrap(status.needs_bootstrap);
          } catch {
            // Silently fail; will default to needsBootstrap=false
          }
        }
      } finally {
        setLoading(false);
      }
    };

    init();
  }, []);

  // Register unauthorized handler so 401 clears the session
  useEffect(() => {
    setUnauthorizedHandler(() => {
      localStorage.removeItem("pos_token");
      setAuthToken(null);
      setToken(null);
      setUser(null);
      setNeedsBootstrap(false);
    });
  }, []);

  const login = async (name: string, pin: string) => {
    const result = await api.login(name, pin);
    const newToken = result.token;
    setAuthToken(newToken);
    setToken(newToken);
    setUser(result.user);
    localStorage.setItem("pos_token", newToken);
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Ignore logout errors
    }
    localStorage.removeItem("pos_token");
    setAuthToken(null);
    setToken(null);
    setUser(null);
    setNeedsBootstrap(false);
  };

  const bootstrapOwner = async (name: string, pin: string) => {
    // Create first owner (no token needed during bootstrap)
    await api.createFirstOwner(name, pin);
    // Then log in as that owner
    await login(name, pin);
    setNeedsBootstrap(false);
  };

  return (
    <AuthContext.Provider
      value={{ user, token, needsBootstrap, loading, login, logout, bootstrapOwner }}
    >
      {children}
    </AuthContext.Provider>
  );
}
