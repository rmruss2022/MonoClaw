import { Link, useLocation } from "react-router-dom";
import { ReactNode } from "react";
import { useApp } from "../context/AppContext";
import { ClaimSubmissionModal } from "./ClaimSubmissionModal";

export function AppShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  const { user, isAuthenticated, logout, claimPrompt, confirmClaimSubmitted, dismissClaimPrompt } = useApp();
  const location = useLocation();
  const role = user?.role ?? "user";

  const canSeeMatches = isAuthenticated && role !== "attorney";
  const canSeeAdmin = isAuthenticated && (role === "admin" || role === "super_user");
  const canSeeGateway = isAuthenticated && (role === "attorney" || role === "admin" || role === "super_user");
  const canSeeQueue = isAuthenticated && (role === "admin" || role === "super_user");

  return (
    <div className="app-frame">
      <header className="top-nav">
        <div>
          <p className="brand">PayMe Lite</p>
          <p className="brand-sub">Settlement Intelligence Console</p>
        </div>
        <nav className="nav-links">
          {canSeeMatches && (
            <Link className={location.pathname === "/" ? "active" : ""} to="/">
              Matches
            </Link>
          )}
          {canSeeAdmin && (
            <Link className={location.pathname === "/admin" ? "active" : ""} to="/admin">
              Admin
            </Link>
          )}
          {canSeeGateway && (
            <Link className={location.pathname === "/gateway" ? "active" : ""} to="/gateway">
              Gateway
            </Link>
          )}
          {canSeeQueue && (
            <Link className={location.pathname === "/queue" ? "active" : ""} to="/queue">
              Queue
            </Link>
          )}
          {isAuthenticated && (
            <button className="ghost-btn" onClick={logout}>
              Sign out {user?.username ? `(${user.username})` : ""}
            </button>
          )}
        </nav>
      </header>
      <main className="page-shell">
        <section className="hero-card">
          <h1>{title}</h1>
          {subtitle ? <p>{subtitle}</p> : null}
        </section>
        <section>{children}</section>
      </main>
      {claimPrompt ? (
        <ClaimSubmissionModal
          title={claimPrompt.title}
          onConfirm={confirmClaimSubmitted}
          onDismiss={dismissClaimPrompt}
        />
      ) : null}
    </div>
  );
}
