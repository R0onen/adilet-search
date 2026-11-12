import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import * as api from '../api/admin';

type Auth = {
  authenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};
const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [authenticated, setAuthenticated] = useState(() => !!api.loadToken());
  const logout = useCallback(() => {
    api.storeToken(null);
    setAuthenticated(false);
    queryClient.removeQueries({ queryKey: ['admin'] });
  }, [queryClient]);
  // A 401 from any admin call (expired or revoked token) ends the session.
  useEffect(() => {
    api.setUnauthorizedHandler(() => setAuthenticated(false));
    return () => api.setUnauthorizedHandler(null);
  }, []);
  const value = useMemo<Auth>(
    () => ({
      authenticated,
      login: async (username, password) => {
        await api.login(username, password);
        setAuthenticated(true);
      },
      logout,
    }),
    [authenticated, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error('useAuth must be used inside AuthProvider');
  return auth;
}

/** Sends an anonymous visitor to the login page and remembers where they were going. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { authenticated } = useAuth();
  const location = useLocation();
  if (!authenticated)
    return (
      <Navigate to="/admin/login" replace state={{ from: location.pathname + location.search }} />
    );
  return <>{children}</>;
}
