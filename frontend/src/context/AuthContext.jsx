/**
 * AuthContext – stores logged-in user + JWT in React state and localStorage.
 */
import { createContext, useContext, useEffect, useState } from "react";
import { authApi } from "../api/client";

const AuthContext = createContext(null);

const TOKEN_KEY = "saferoute_token";
const USER_KEY = "saferoute_user";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [loading, setLoading] = useState(Boolean(localStorage.getItem(TOKEN_KEY)));

  // On load, verify token with /auth/me
  useEffect(() => {
    let cancelled = false;

    async function verify() {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const data = await authApi.me(token);
        if (!cancelled) {
          setUser(data.user);
          localStorage.setItem(USER_KEY, JSON.stringify(data.user));
        }
      } catch {
        if (!cancelled) {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    verify();
    return () => {
      cancelled = true;
    };
  }, [token]);

  function saveSession(accessToken, nextUser) {
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    setToken(accessToken);
    setUser(nextUser);
  }

  async function register(form) {
    const data = await authApi.register(form);
    saveSession(data.access_token, data.user);
    return data;
  }

  async function login(form) {
    const data = await authApi.login(form);
    saveSession(data.access_token, data.user);
    return data;
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }

  const value = {
    user,
    token,
    loading,
    isAuthenticated: Boolean(user && token),
    register,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
