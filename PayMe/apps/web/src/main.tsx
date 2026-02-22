import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppProvider, useApp } from "./context/AppContext";
import { AdminPage } from "./pages/AdminPage";
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
  const { authStatus, isAuthenticated } = useApp();
  if (authStatus === "booting") return <div className="loader">Loading...</div>;
  if (isAuthenticated) return <Navigate to="/matches" replace />;
  return <Outlet />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/login" element={<LoginPage />} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/matches" element={<MatchesPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/settlements/:id" element={<SettlementDetailPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/matches" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProvider>
      <App />
    </AppProvider>
  </React.StrictMode>
);
