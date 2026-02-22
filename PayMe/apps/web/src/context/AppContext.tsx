import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api";
import {
  AdminEvent,
  AdminOverview,
  AdminSettlement,
  AdminUser,
  AuthUser,
  Match,
  OngoingClaim,
  UserStats,
} from "../types";

type AuthStatus = "booting" | "ready";

type AppContextValue = {
  authStatus: AuthStatus;
  token: string;
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  signup: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  matches: Match[];
  matchesLoading: boolean;
  loadMatches: () => Promise<void>;
  rerunMatch: () => Promise<void>;
  syncGmailAndMatch: () => Promise<void>;
  syncBankAndMatch: () => Promise<void>;
  ongoingClaims: OngoingClaim[];
  loadOngoingClaims: () => Promise<void>;
  markClaimOutcome: (settlementId: string, outcome: "paid_out" | "not_paid_out") => Promise<void>;
  claimPrompt: { settlementId: string; title: string } | null;
  beginClaimFlow: (input: { settlementId: string; title: string; claimUrl?: string | null }) => void;
  confirmClaimSubmitted: () => Promise<void>;
  dismissClaimPrompt: () => void;
  adminLoading: boolean;
  adminOverview: AdminOverview | null;
  adminUsers: AdminUser[];
  adminSettlements: AdminSettlement[];
  adminEvents: AdminEvent[];
  selectedUserStats: UserStats | null;
  loadAdminDashboard: () => Promise<void>;
  loadUserStats: (userId: string) => Promise<void>;
};

const AppContext = createContext<AppContextValue | null>(null);

async function tokenToUser(token: string): Promise<AuthUser> {
  localStorage.setItem("token", token);
  return apiFetch<AuthUser>("/auth/me");
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [authStatus, setAuthStatus] = useState<AuthStatus>("booting");
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [user, setUser] = useState<AuthUser | null>(null);

  const [matches, setMatches] = useState<Match[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [ongoingClaims, setOngoingClaims] = useState<OngoingClaim[]>([]);
  const [claimPrompt, setClaimPrompt] = useState<{ settlementId: string; title: string } | null>(null);

  const [adminLoading, setAdminLoading] = useState(false);
  const [adminOverview, setAdminOverview] = useState<AdminOverview | null>(null);
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [adminSettlements, setAdminSettlements] = useState<AdminSettlement[]>([]);
  const [adminEvents, setAdminEvents] = useState<AdminEvent[]>([]);
  const [selectedUserStats, setSelectedUserStats] = useState<UserStats | null>(null);

  const clearAuth = () => {
    localStorage.removeItem("token");
    setToken("");
    setUser(null);
  };

  const refreshUser = async () => {
    const saved = localStorage.getItem("token") || "";
    if (!saved) {
      clearAuth();
      return;
    }
    try {
      const me = await apiFetch<AuthUser>("/auth/me");
      setToken(saved);
      setUser(me);
    } catch {
      clearAuth();
    }
  };

  useEffect(() => {
    refreshUser().finally(() => setAuthStatus("ready"));
  }, []);

  const login = async (usernameOrEmail: string, password: string) => {
    const res = await apiFetch<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username_or_email: usernameOrEmail, password }),
    });
    const me = await tokenToUser(res.access_token);
    setToken(res.access_token);
    setUser(me);
  };

  const signup = async (username: string, email: string, password: string) => {
    const res = await apiFetch<{ access_token: string }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    const me = await tokenToUser(res.access_token);
    setToken(res.access_token);
    setUser(me);
  };

  const loadMatches = async () => {
    setMatchesLoading(true);
    try {
      const rows = await apiFetch<Match[]>("/match/results");
      setMatches(rows);
    } finally {
      setMatchesLoading(false);
    }
  };

  const loadOngoingClaims = async () => {
    const rows = await apiFetch<OngoingClaim[]>("/claims/ongoing");
    setOngoingClaims(rows);
  };

  const rerunMatch = async () => {
    setMatchesLoading(true);
    try {
      await apiFetch("/match/run", { method: "POST" });
      const rows = await apiFetch<Match[]>("/match/results");
      setMatches(rows);
      await loadOngoingClaims();
    } finally {
      setMatchesLoading(false);
    }
  };

  const syncGmailAndMatch = async () => {
    setMatchesLoading(true);
    try {
      await apiFetch("/integrations/gmail/sync", { method: "POST" });
      await apiFetch("/match/run", { method: "POST" });
      const rows = await apiFetch<Match[]>("/match/results");
      setMatches(rows);
      await loadOngoingClaims();
      await refreshUser();
    } finally {
      setMatchesLoading(false);
    }
  };

  const syncBankAndMatch = async () => {
    setMatchesLoading(true);
    try {
      await apiFetch("/integrations/plaid/sync", { method: "POST" });
      await apiFetch("/match/run", { method: "POST" });
      const rows = await apiFetch<Match[]>("/match/results");
      setMatches(rows);
      await loadOngoingClaims();
      await refreshUser();
    } finally {
      setMatchesLoading(false);
    }
  };

  const loadAdminDashboard = async () => {
    setAdminLoading(true);
    try {
      const [overviewData, usersData, settlementsData, eventsData] = await Promise.all([
        apiFetch<AdminOverview>("/admin/stats/overview"),
        apiFetch<AdminUser[]>("/admin/users?limit=100"),
        apiFetch<AdminSettlement[]>("/admin/settlements?limit=100"),
        apiFetch<AdminEvent[]>("/admin/events?limit=50"),
      ]);
      setAdminOverview(overviewData);
      setAdminUsers(usersData);
      setAdminSettlements(settlementsData);
      setAdminEvents(eventsData);
    } finally {
      setAdminLoading(false);
    }
  };

  const loadUserStats = async (userId: string) => {
    const stats = await apiFetch<UserStats>(`/admin/stats/users/${userId}`);
    setSelectedUserStats(stats);
  };

  const beginClaimFlow = (input: { settlementId: string; title: string; claimUrl?: string | null }) => {
    if (input.claimUrl) {
      window.open(input.claimUrl, "_blank", "noopener,noreferrer");
    }
    apiFetch(`/settlements/${input.settlementId}/claim/opened`, { method: "POST" }).catch(() => {
      // Non-blocking analytics event; don't block the claim flow on failure.
    });
    setClaimPrompt({ settlementId: input.settlementId, title: input.title });
  };

  const dismissClaimPrompt = () => setClaimPrompt(null);

  const confirmClaimSubmitted = async () => {
    if (!claimPrompt) return;
    await apiFetch(`/settlements/${claimPrompt.settlementId}/claim/submitted`, { method: "POST" });
    setClaimPrompt(null);
    await Promise.all([loadMatches(), loadOngoingClaims()]);
  };

  const markClaimOutcome = async (settlementId: string, outcome: "paid_out" | "not_paid_out") => {
    await apiFetch(`/settlements/${settlementId}/claim/outcome`, {
      method: "POST",
      body: JSON.stringify({ outcome }),
    });
    await Promise.all([loadMatches(), loadOngoingClaims()]);
  };

  const value = useMemo<AppContextValue>(
    () => ({
      authStatus,
      token,
      user,
      isAuthenticated: Boolean(token && user),
      login,
      signup,
      logout: clearAuth,
      refreshUser,
      matches,
      matchesLoading,
      loadMatches,
      rerunMatch,
      syncGmailAndMatch,
      syncBankAndMatch,
      ongoingClaims,
      loadOngoingClaims,
      markClaimOutcome,
      claimPrompt,
      beginClaimFlow,
      confirmClaimSubmitted,
      dismissClaimPrompt,
      adminLoading,
      adminOverview,
      adminUsers,
      adminSettlements,
      adminEvents,
      selectedUserStats,
      loadAdminDashboard,
      loadUserStats,
    }),
    [
      authStatus,
      token,
      user,
      matches,
      matchesLoading,
      ongoingClaims,
      claimPrompt,
      adminLoading,
      adminOverview,
      adminUsers,
      adminSettlements,
      adminEvents,
      selectedUserStats,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error("useApp must be used within AppProvider");
  }
  return ctx;
}
