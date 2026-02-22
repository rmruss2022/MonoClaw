import { useEffect, useState } from "react";
import { AppShell } from "../components/AppShell";
import { SettlementCard } from "../components/SettlementCard";
import { useApp } from "../context/AppContext";

export function MatchesPage() {
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"matches" | "ongoing_claims">("matches");
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
  } = useApp();
  const gmailConnected = Boolean(user?.gmail_synced_at);
  const bankConnected = Boolean(user?.plaid_synced_at);

  useEffect(() => {
    Promise.all([loadMatches(), loadOngoingClaims()]).catch((err) => setError((err as Error).message));
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

  return (
    <AppShell
      title="Top Matching Settlements"
      subtitle="Pinned items stay on top. Sync providers to refresh signals and rerun scoring."
    >
      <section className="panel">
        <div className="toolbar">
          {!gmailConnected ? (
            <button onClick={syncGmail} disabled={matchesLoading}>
              {matchesLoading ? "Working..." : "Connect Gmail"}
            </button>
          ) : null}
          {!bankConnected ? (
            <button onClick={syncPlaid} disabled={matchesLoading}>
              {matchesLoading ? "Working..." : "Connect Bank"}
            </button>
          ) : null}
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
        </div>
        {error ? <p className="error">{error}</p> : null}
        {activeTab === "ongoing_claims" ? (
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
        ) : (
          <section className="matches-grid">
            {matches.map((item) => (
              <SettlementCard key={item.settlement_id} item={item} onChange={loadMatches} />
            ))}
            {!matches.length && !matchesLoading ? (
              <p className="muted">No results yet. Run onboarding sync or trigger a rerun.</p>
            ) : null}
          </section>
        )}
        <div className="bottom-cta">
          <button onClick={rerunMatch} disabled={matchesLoading}>
            {matchesLoading ? "Working..." : "Find New Settlements"}
          </button>
        </div>
      </section>
    </AppShell>
  );
}
