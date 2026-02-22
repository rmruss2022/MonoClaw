import { useEffect, useState } from "react";
import { AppShell } from "../components/AppShell";
import { SettlementCard } from "../components/SettlementCard";
import { useApp } from "../context/AppContext";

export function MatchesPage() {
  const [error, setError] = useState("");
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
    markClaimOutcome,
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
          <button className="ghost-btn" onClick={rerunMatch} disabled={matchesLoading}>
            Rerun Match
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {ongoingClaims.length ? (
          <section className="panel ongoing-claims">
            <h3>Ongoing Claims</h3>
            {ongoingClaims.map((claim) => (
              <article key={claim.settlement_id} className="ongoing-claim-row">
                <div>
                  <p>{claim.title}</p>
                  <p className="muted">Submitted: {claim.claim_submitted_at ? new Date(claim.claim_submitted_at).toLocaleDateString() : "Recently"}</p>
                </div>
                <div className="toolbar">
                  <button className="ghost-btn" onClick={() => markClaimOutcome(claim.settlement_id, "not_paid_out")}>
                    Not Paid Out
                  </button>
                  <button onClick={() => markClaimOutcome(claim.settlement_id, "paid_out")}>Paid Out</button>
                </div>
              </article>
            ))}
          </section>
        ) : null}
        <section className="matches-grid">
          {matches.map((item) => (
            <SettlementCard key={item.settlement_id} item={item} onChange={loadMatches} />
          ))}
          {!matches.length && !matchesLoading ? (
            <p className="muted">No results yet. Run onboarding sync or trigger a rerun.</p>
          ) : null}
        </section>
      </section>
    </AppShell>
  );
}
