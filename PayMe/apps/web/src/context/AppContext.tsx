import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api";
import {
  AdminEvent,
  AdminOverview,
  AdminSettlement,
  AdminUser,
  AuthUser,
  AutofillJob,
  Match,
  OngoingClaim,
  SettlementQuestion,
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
  beginClaimFlow: (input: { settlementId: string; title: string; claimUrl?: string | null }) => Promise<void>;
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
  autofillJobs: AutofillJob[];
  autofillLoading: boolean;
  gmailOAuthPending: boolean;
  loadAutofillJobs: () => Promise<void>;
  enqueueAutofillJob: (settlementId: string) => Promise<AutofillJob>;
  initiateGmailOAuth: () => Promise<void>;
  revokeGmail: () => Promise<void>;
  initiatePlaidLink: () => Promise<void>;
  disconnectPlaid: () => Promise<void>;
};

const AppContext = createContext<AppContextValue | null>(null);

async function tokenToUser(token: string): Promise<AuthUser> {
  localStorage.setItem("token", token);
  return apiFetch<AuthUser>("/auth/me");
}

export function AppProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
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

  const [autofillJobs, setAutofillJobs] = useState<AutofillJob[]>([]);
  const [autofillLoading, setAutofillLoading] = useState(false);
  const [gmailOAuthPending, setGmailOAuthPending] = useState(false);

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

    // If Gmail is already connected, kick off a background refresh + rerank
    // so users land on up-to-date matches after login.
    if (me.gmail_oauth_connected) {
      void (async () => {
        try {
          await apiFetch("/integrations/gmail/sync", { method: "POST" });
          await apiFetch("/match/run", { method: "POST" });
        } catch {
          // Non-blocking sync: login should still succeed even if sync fails.
        } finally {
          await refreshUser().catch(() => {});
        }
      })();
    }
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

  const beginClaimFlow = async (input: { settlementId: string; title: string; claimUrl?: string | null }) => {
    try {
      const questions = await apiFetch<SettlementQuestion[]>(`/settlements/${input.settlementId}/questions`);
      if (questions.length > 0) {
        navigate(`/claim/${input.settlementId}`);
        return;
      }
    } catch {
      // fall through to legacy flow
    }
    // Legacy external-URL flow
    if (input.claimUrl) {
      window.open(input.claimUrl, "_blank", "noopener,noreferrer");
    }
    apiFetch(`/settlements/${input.settlementId}/claim/opened`, { method: "POST" }).catch(() => {});
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

  const loadAutofillJobs = async () => {
    setAutofillLoading(true);
    try {
      const jobs = await apiFetch<AutofillJob[]>("/autofill/jobs");
      setAutofillJobs(jobs);
    } finally {
      setAutofillLoading(false);
    }
  };

  const enqueueAutofillJob = async (settlementId: string): Promise<AutofillJob> => {
    try {
      const job = await apiFetch<AutofillJob>("/autofill/jobs", {
        method: "POST",
        body: JSON.stringify({ settlement_id: settlementId }),
      });
      await loadAutofillJobs();
      return job;
    } catch (err: unknown) {
      // On 409 conflict, the existing job is returned in detail.job
      if (err && typeof err === "object" && "status" in err && (err as { status: number }).status === 409) {
        const apiErr = err as { detail?: { job?: AutofillJob } };
        if (apiErr.detail?.job) {
          await loadAutofillJobs();
          return apiErr.detail.job;
        }
      }
      throw err;
    }
  };

  const initiateGmailOAuth = async () => {
    setGmailOAuthPending(true);
    // Open a normal browser tab synchronously (not a popup window).
    const oauthTab = window.open("about:blank", "_blank");
    if (!oauthTab) {
      setGmailOAuthPending(false);
      return;
    }
    let cleanup: (() => void) | null = null;
    let timeoutId: number | undefined;
    try {
      const { auth_url } = await apiFetch<{ auth_url: string }>("/integrations/gmail/oauth/init");
      oauthTab.location.href = auth_url;
      const apiOrigin = (() => {
        try {
          return new URL(import.meta.env.VITE_API_BASE_URL || window.location.origin).origin;
        } catch {
          return window.location.origin;
        }
      })();
      const handler = async (e: MessageEvent) => {
        // Accept events from API callback origin (or same-origin in dev fallback).
        if (e.origin !== apiOrigin && e.origin !== window.location.origin) return;
        if (e.data?.type === "gmail_oauth_success") {
          cleanup?.();
          await refreshUser();
        } else if (e.data?.type === "gmail_oauth_error") {
          cleanup?.();
        }
      };
      window.addEventListener("message", handler);
      // Fallback cleanup in case popup is closed or provider blocks opener messaging.
      timeoutId = window.setTimeout(() => {
        cleanup?.();
      }, 120000);
      cleanup = () => {
        window.removeEventListener("message", handler);
        if (timeoutId) window.clearTimeout(timeoutId);
        setGmailOAuthPending(false);
      };
    } catch {
      oauthTab.close();
      setGmailOAuthPending(false);
    }
  };

  const revokeGmail = async () => {
    await apiFetch("/integrations/gmail/revoke", { method: "POST" });
    await refreshUser();
  };

  const initiatePlaidLink = async () => {
    const { link_token } = await apiFetch<{ link_token: string }>("/integrations/plaid/link-token", {
      method: "POST",
    });
    if (!document.querySelector("script[data-plaid]")) {
      const s = document.createElement("script");
      s.src = "https://cdn.plaid.com/link/v2/stable/link-initialize.js";
      s.dataset.plaid = "1";
      document.head.appendChild(s);
      await new Promise<void>((r) => {
        s.onload = () => r();
      });
    }
    (window as unknown as { Plaid: { create: (cfg: object) => { open: () => void } } }).Plaid.create({
      token: link_token,
      onSuccess: async (publicToken: string, meta: { institution?: { institution_id: string; name: string } }) => {
        await apiFetch("/integrations/plaid/exchange", {
          method: "POST",
          body: JSON.stringify({
            public_token: publicToken,
            institution_id: meta.institution?.institution_id,
            institution_name: meta.institution?.name,
          }),
        });
        await refreshUser();
      },
      onExit: () => {},
    }).open();
  };

  const disconnectPlaid = async () => {
    await apiFetch("/integrations/plaid/disconnect", { method: "POST" });
    await refreshUser();
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
      autofillJobs,
      autofillLoading,
      gmailOAuthPending,
      loadAutofillJobs,
      enqueueAutofillJob,
      initiateGmailOAuth,
      revokeGmail,
      initiatePlaidLink,
      disconnectPlaid,
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
      autofillJobs,
      autofillLoading,
      gmailOAuthPending,
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
