import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppProvider, useApp } from "./context/AppContext";
import { AdminPage } from "./pages/AdminPage";
import { ClaimFormPage } from "./pages/ClaimFormPage";
import { GatewayPage } from "./pages/GatewayPage";
import { LoginPage } from "./pages/LoginPage";
import { MatchesPage } from "./pages/MatchesPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { SettlementDetailPage } from "./pages/SettlementDetailPage";
import { SignupPage } from "./pages/SignupPage";
import "./styles.css";

function ProtectedRoute() {
  const { authStatus, isAuthenticated } = useApp();
  if (authStatus === "booting") return <div className="loader">Restoring session...</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function PublicOnlyRoute() {
  const { authStatus, isAuthenticated, user } = useApp();
  if (authStatus === "booting") return <div className="loader">Loading...</div>;
  if (isAuthenticated) {
    // Attorneys go straight to the Gateway
    if (user?.role === "attorney") return <Navigate to="/gateway" replace />;
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

/** Requires login + one of the allowed roles. */
function RoleRoute({ roles }: { roles: string[] }) {
  const { authStatus, isAuthenticated, user } = useApp();
  if (authStatus === "booting") return <div className="loader">Loading...</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!roles.includes(user?.role ?? "user")) return <Navigate to="/" replace />;
  return <Outlet />;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Signup wizard — standalone (no redirect after auth completes in wizard) */}
      <Route path="/signup" element={<SignupPage />} />

      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      {/* Standard authenticated routes (all roles except attorney-only) */}
      <Route element={<ProtectedRoute />}>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/" element={<MatchesPage />} />
        <Route path="/settlements/:id" element={<SettlementDetailPage />} />
        <Route path="/claim/:settlementId" element={<ClaimFormPage />} />
      </Route>

      {/* Admin-only */}
      <Route element={<RoleRoute roles={["admin", "super_user"]} />}>
        <Route path="/admin" element={<AdminPage />} />
      </Route>

      {/* Gateway — attorneys, admins, super_users */}
      <Route element={<RoleRoute roles={["attorney", "admin", "super_user"]} />}>
        <Route path="/gateway" element={<GatewayPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppProvider>
        <AppRoutes />
      </AppProvider>
    </BrowserRouter>
  </React.StrictMode>
);
