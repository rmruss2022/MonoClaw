import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import { AppShell } from "../components/AppShell";
import { SettlementCard } from "../components/SettlementCard";
import { useApp } from "../context/AppContext";
import type { ClaimHistoryItem } from "../types";

export function MatchesPage() {
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"matches" | "ongoing_claims" | "history" | "autofill">("matches");
  const [claimHistory, setClaimHistory] = useState<ClaimHistoryItem[]>([]);
  const {
    matches,
    matchesLoading,
    loadMatches,
    rerunMatch,
    syncGmailAndMatch,
    syncBankAndMatch,
    user,
    ongoingClaims,
    loadOngoingClaims,
    loadAutofillJobs,
    autofillJobs,
    autofillLoading,
    initiateGmailOAuth,
    initiatePlaidLink,
  } = useApp();
  const gmailConnected = user?.gmail_oauth_connected ?? Boolean(user?.gmail_synced_at);
  const bankConnected = user?.plaid_linked ?? Boolean(user?.plaid_synced_at);

  // Exclude matches already in-flight (submitted) or resolved (paid_out / not_paid_out)
  const visibleMatches = matches.filter((m) => !m.claim_status);

  const totalMinCents = visibleMatches.reduce((sum, m) => sum + (m.payout_min_cents ?? 0), 0);
  const totalMaxCents = visibleMatches.reduce((sum, m) => sum + (m.payout_max_cents ?? 0), 0);
  const fmtUsd = (cents: number) => `$${(cents / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  const fmtUsdExact = (cents: number) =>
    `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  useEffect(() => {
    Promise.all([
      loadMatches(),
      loadOngoingClaims(),
      loadAutofillJobs(),
      apiFetch<ClaimHistoryItem[]>("/claims/history").then(setClaimHistory).catch(() => {}),
    ]).catch((err) => setError((err as Error).message));
  }, []);

  const syncGmail = async () => {
    setError("");
    try {
      await syncGmailAndMatch();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const syncPlaid = async () => {
    setError("");
    try {
      await syncBankAndMatch();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const connectPlaid = async () => {
    setError("");
    try {
      await initiatePlaidLink();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const connectGmail = async () => {
    setError("");
    await initiateGmailOAuth();
  };

  const renderTabContent = () => {
    if (activeTab === "ongoing_claims") {
      return (
        <section className="panel ongoing-claims">
          <h3>Ongoing Claims</h3>
          {ongoingClaims.length ? (
            ongoingClaims.map((claim) => (
              <article key={claim.settlement_id} className="ongoing-claim-row">
                <div>
                  <p>{claim.title}</p>
                  <p className="muted">
                    Submitted: {claim.claim_submitted_at ? new Date(claim.claim_submitted_at).toLocaleDateString() : "Recently"}
                  </p>
                </div>
                <div className="claim-status-container">
                  <span className={`status-pill status-${claim.claim_status}`}>
                    {claim.claim_status.replace("_", " ")}
                  </span>
                </div>
              </article>
            ))
          ) : (
            <p className="muted">No ongoing claims yet.</p>
          )}
        </section>
      );
    } else if (activeTab === "history") {
      const totalPaid = claimHistory
        .filter((c) => c.claim_status === "paid_out" && c.amount_paid_cents != null)
        .reduce((s, c) => s + (c.amount_paid_cents ?? 0), 0);
      return (
        <section className="panel ongoing-claims">
          <h3>Claim History</h3>
          {totalPaid > 0 && (
            <p style={{ color: "var(--accent-2)", fontWeight: 700, marginBottom: "0.75rem" }}>
              Total received: ${(totalPaid / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          )}
          {claimHistory.length ? (
            claimHistory.map((claim) => (
              <article key={claim.settlement_id} className="ongoing-claim-row">
                <div style={{ flex: 1 }}>
                  <p style={{ margin: "0 0 0.2rem" }}>{claim.title}</p>
                  <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
                    Submitted: {claim.claim_submitted_at ? new Date(claim.claim_submitted_at).toLocaleDateString() : "—"}
                    {claim.claim_outcome_at && (
                      <> &middot; Resolved: {new Date(claim.claim_outcome_at).toLocaleDateString()}</>
                    )}
                  </p>
                </div>
                <div className="claim-status-container" style={{ textAlign: "right" }}>
                  <span className={`status-pill status-${claim.claim_status}`}>
                    {claim.claim_status === "paid_out" ? "Paid Out" : "Not Paid Out"}
                  </span>
                  {claim.amount_paid_cents != null && (
                    <p style={{ margin: "0.25rem 0 0", fontWeight: 700, color: "var(--accent-2)", fontSize: "0.9rem" }}>
                      ${(claim.amount_paid_cents / 100).toFixed(2)}
                    </p>
                  )}
                </div>
              </article>
            ))
          ) : (
            <p className="muted">No resolved claims yet.</p>
          )}
        </section>
      );
    } else if (activeTab === "autofill") {
      return (
        <section>
          {autofillLoading ? <p className="muted">Loading...</p> : null}
          {!autofillJobs.length && !autofillLoading ? (
            <p className="muted">No autofill jobs yet. Click "Start Autofill" on a match card.</p>
          ) : null}
          {[...autofillJobs].sort((a, b) => b.created_at.localeCompare(a.created_at)).map(job => (
            <div key={job.id} className={`autofill-job-card status-${job.status}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700 }}>{job.settlement_id.slice(0, 8)}…</span>
                <span className={`status-pill status-${job.status}`}>{job.status}</span>
              </div>
              <div className="job-meta">
                <span>Attempts: {job.attempt_count}</span>
                {job.started_at ? <span>Started: {new Date(job.started_at).toLocaleString()}</span> : null}
                {job.completed_at ? <span>Done: {new Date(job.completed_at).toLocaleString()}</span> : null}
                {job.error_message ? <span style={{ color: 'var(--danger)' }}>{job.error_message}</span> : null}
              </div>
              {job.steps.length > 0 && (
                <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1rem', fontSize: '0.8rem', color: 'var(--muted)' }}>
                  {job.steps.map(step => (
                    <li key={step.id}>{step.step_name}: <strong>{step.status}</strong>{step.error_message ? ` — ${step.error_message}` : ''}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </section>
      );
    } else {
      return (
        <section className="matches-grid">
          {visibleMatches.map((item) => (
            <SettlementCard key={item.settlement_id} item={item} onChange={loadMatches} />
          ))}
          {!visibleMatches.length && !matchesLoading ? (
            <p className="muted">No new matches — all settlements have active or resolved claims.</p>
          ) : null}
        </section>
      );
    }
  };

  return (
    <AppShell
      title="Top Matching Settlements"
      subtitle="Pinned items stay on top. Sync providers to refresh signals and rerun scoring."
    >
      <section className="panel">
        {(() => {
          const totalSaved = claimHistory
            .filter((c) => c.claim_status === "paid_out" && c.amount_paid_cents != null)
            .reduce((s, c) => s + (c.amount_paid_cents ?? 0), 0);
          return totalSaved > 0 ? (
            <div style={{
              background: "rgba(133,255,158,0.10)",
              border: "1px solid rgba(133,255,158,0.35)",
              borderRadius: "10px",
              padding: "0.65rem 1rem",
              marginBottom: "0.75rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}>
              <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>Total recovered for you</span>
              <span style={{ fontWeight: 800, fontSize: "1.1rem", color: "var(--accent-2)" }}>
                {fmtUsdExact(totalSaved)}
              </span>
            </div>
          ) : null;
        })()}
        {visibleMatches.length > 0 && (
          <div className="payout-banner">
            <span className="payout-label">Potential payout across {visibleMatches.length} open matches:</span>
            <span className="payout-range">{fmtUsd(totalMinCents)} – {fmtUsd(totalMaxCents)}</span>
          </div>
        )}
        <div className="toolbar">
          {!gmailConnected ? (
            <button onClick={connectGmail} disabled={matchesLoading}>
              Connect Gmail
            </button>
          ) : (
            <button className="ghost-btn" onClick={syncGmail} disabled={matchesLoading}>
              Sync Gmail & Refresh
            </button>
          )}
        </div>
        <div className="tab-row" role="tablist" aria-label="Matches navigation">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "matches"}
            className={`tab-btn ${activeTab === "matches" ? "active" : ""}`}
            onClick={() => setActiveTab("matches")}
          >
            Matches
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "ongoing_claims"}
            className={`tab-btn ${activeTab === "ongoing_claims" ? "active" : ""}`}
            onClick={() => setActiveTab("ongoing_claims")}
          >
            Ongoing Claims
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "history"}
            className={`tab-btn ${activeTab === "history" ? "active" : ""}`}
            onClick={() => setActiveTab("history")}
          >
            History {claimHistory.length > 0 ? `(${claimHistory.length})` : ""}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "autofill"}
            className={`tab-btn ${activeTab === "autofill" ? "active" : ""}`}
            onClick={() => setActiveTab("autofill")}
          >
            Autofill Jobs ({autofillJobs.filter(j => j.status === "running" || j.status === "queued").length})
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {renderTabContent()}
        <div style={{
          borderTop: "1px solid var(--border)",
          marginTop: "1.25rem",
          paddingTop: "1rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "0.75rem",
        }}>
          <div>
            {bankConnected ? (
              <>
                <p style={{ margin: 0, fontWeight: 600, fontSize: "0.9rem" }}>
                  {user?.plaid_institution_name ?? "Linked Bank Account"}
                </p>
                {user?.plaid_balance_available_cents != null && (
                  <p style={{ margin: "0.1rem 0 0", fontWeight: 700, fontSize: "0.9rem", color: "var(--accent-2)" }}>
                    {fmtUsdExact(user.plaid_balance_available_cents)}
                    <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: "0.75rem", marginLeft: "0.35rem" }}>available</span>
                  </p>
                )}
                <p className="muted" style={{ margin: "0.1rem 0 0", fontSize: "0.78rem" }}>
                  Last synced{" "}
                  {user?.plaid_synced_at
                    ? new Date(user.plaid_synced_at).toLocaleDateString(undefined, {
                        month: "short", day: "numeric", year: "numeric",
                      })
                    : "—"}
                </p>
              </>
            ) : (
              <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--muted)" }}>
                No bank account linked
              </p>
            )}
          </div>
          {bankConnected ? (
            <button className="ghost-btn" onClick={syncPlaid} disabled={matchesLoading} style={{ whiteSpace: "nowrap" }}>
              Sync Bank
            </button>
          ) : (
            <button onClick={connectPlaid} disabled={matchesLoading} style={{ whiteSpace: "nowrap" }}>
              Connect Bank
            </button>
          )}
        </div>
        <div className="bottom-cta">
          <button onClick={rerunMatch} disabled={matchesLoading}>
            {matchesLoading ? "Working..." : "Find New Settlements"}
          </button>
        </div>
      </section>
    </AppShell>
  );
}
