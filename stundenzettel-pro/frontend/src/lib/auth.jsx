/** Angemeldeter Nutzer, Firma und Lizenzstand für die ganze Oberfläche – mit Offline-Gedächtnis fürs Stempeln ohne Netz. */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, hasToken, onUnauthorized, setToken } from './api';

const AuthContext = createContext(null);
const SESSION_KEY = 'szpro-session';

const sessionLesen = () => { try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch { return null; } };
const sessionMerken = (daten) => { try { if (daten) localStorage.setItem(SESSION_KEY, JSON.stringify({ user: daten.user, firma: daten.firma, plan: daten.plan })); else localStorage.removeItem(SESSION_KEY); } catch { /* ignore */ } };

export function AuthProvider({ children }) {
  const [state, setState] = useState({ ready: false, user: null, firma: null, plan: null, offline: false });

  const uebernehmen = useCallback((daten) => {
    if (daten?.token) setToken(daten.token);
    sessionMerken(daten);
    setState({ ready: true, user: daten?.user || null, firma: daten?.firma || null, plan: daten?.plan || null, offline: false });
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    sessionMerken(null);
    setState({ ready: true, user: null, firma: null, plan: null, offline: false });
  }, []);

  const refresh = useCallback(async () => {
    if (!hasToken()) { setState((s) => ({ ...s, ready: true })); return null; }
    try {
      const daten = await api.get('/api/auth/ich');
      sessionMerken(daten);
      setState({ ready: true, user: daten.user, firma: daten.firma, plan: daten.plan, offline: false });
      return daten;
    } catch (err) {
      if (err.status === 401) { logout(); return null; }
      // kein Netz: mit dem gemerkten Stand weiterarbeiten (Stempeluhr läuft offline weiter)
      const alt = err.status === 0 ? sessionLesen() : null;
      setState((s) => ({ ...s, ready: true, user: alt?.user || s.user, firma: alt?.firma || s.firma, plan: alt?.plan || s.plan, offline: err.status === 0 }));
      return null;
    }
  }, [logout]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => onUnauthorized(logout), [logout]);
  useEffect(() => {
    const online = () => { if (hasToken()) refresh(); };
    window.addEventListener('online', online);
    return () => window.removeEventListener('online', online);
  }, [refresh]);

  const value = useMemo(() => ({
    ...state,
    isBuero: ['buero', 'inhaber'].includes(state.user?.role),
    isInhaber: state.user?.role === 'inhaber',
    isVorarbeiter: state.user?.role === 'vorarbeiter',
    canWrite: state.plan ? state.plan.schreiben !== false : true,
    login: async (email, password) => uebernehmen(await api.post('/api/auth/login', { email, password })),
    register: async (daten) => uebernehmen(await api.post('/api/auth/registrieren', daten)),
    acceptInvite: async (token, password) => uebernehmen(await api.post(`/api/auth/einladung/${token}`, { password })),
    logout,
    refresh,
    setFirma: (firma, plan) => setState((s) => { const n = { ...s, firma: firma || s.firma, plan: plan || s.plan }; sessionMerken(n); return n; }),
  }), [state, uebernehmen, logout, refresh]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
