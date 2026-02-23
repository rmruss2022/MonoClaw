import { useEffect, useState } from "react";
import { AppShell } from "../components/AppShell";
import { useApp } from "../context/AppContext";
import { apiFetch } from "../api";
import { MlSample } from "../types";

export function AdminPage() {
  const {
    adminLoading,
    adminOverview,
    adminUsers,
    adminSettlements,
    adminEvents,
    selectedUserStats,
    loadAdminDashboard,
    loadUserStats: loadUserStatsFromContext,
  } = useApp();
  const [selectedUser, setSelectedUser] = useState<string>("");
  const [error, setError] = useState("");
  const [mlSamples, setMlSamples] = useState<MlSample[] | null>(null);
  const [mlCount, setMlCount] = useState(0);
  const [mlLoading, setMlLoading] = useState(false);
  const [exportJson, setExportJson] = useState("");

  const load = async () => {
    setError("");
    try {
      await loadAdminDashboard();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleLoadUserStats = async () => {
    if (!selectedUser) return;
    try {
      await loadUserStatsFromContext(selectedUser);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const loadDataset = async () => {
    setMlLoading(true);
    try {
      const data = await apiFetch<{ count: number; rows: MlSample[] }>("/admin/ml/dataset");
      setMlSamples(data.rows);
      setMlCount(data.count);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setMlLoading(false);
    }
  };

  const exportLabeled = async () => {
    setMlLoading(true);
    try {
      const data = await apiFetch<{ count: number; samples: MlSample[] }>("/admin/ml/export-labeled");
      setExportJson(JSON.stringify(data, null, 2));
      setMlSamples(data.samples);
      setMlCount(data.count);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setMlLoading(false);
    }
  };

  return (
    <AppShell title="Admin Observatory" subtitle="Live operational visibility for users, settlements, and matching.">
      <section className="panel stack">
        <div className="toolbar">
          <button onClick={load} disabled={adminLoading}>
            {adminLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
        {error ? <p className="error">{error}. Ensure `ADMIN_DEBUG=true`.</p> : null}
        <section className="stats-grid">
          {Object.entries(adminOverview || {}).map(([key, value]) => (
            <article key={key} className="stat-card">
              <h3>{key.replace(/_/g, " ")}</h3>
              <p>{value}</p>
            </article>
          ))}
        </section>
      </section>

      <section className="panel stack">
        <h2>Users</h2>
        <table>
          <thead>
            <tr>
              <th>Username</th>
              <th>Email</th>
              <th>State</th>
              <th>Matches</th>
            </tr>
          </thead>
          <tbody>
            {adminUsers.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.email}</td>
                <td>{u.state || "-"}</td>
                <td>{u.match_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="toolbar">
          <select value={selectedUser} onChange={(e) => setSelectedUser(e.target.value)}>
            <option value="">Select user for stats</option>
            {adminUsers.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
          <button onClick={handleLoadUserStats}>Load user stats</button>
        </div>
        {selectedUserStats ? (
          <section className="stats-grid">
            <article className="stat-card">
              <h3>Match results</h3>
              <p>{selectedUserStats.total_match_results}</p>
            </article>
            <article className="stat-card">
              <h3>Latest run rows</h3>
              <p>{selectedUserStats.latest_run_result_count}</p>
            </article>
            <article className="stat-card">
              <h3>Average score</h3>
              <p>{selectedUserStats.average_score.toFixed(2)}</p>
            </article>
            <article className="stat-card">
              <h3>Gmail messages</h3>
              <p>{selectedUserStats.gmail_messages}</p>
            </article>
            <article className="stat-card">
              <h3>Plaid transactions</h3>
              <p>{selectedUserStats.plaid_transactions}</p>
            </article>
          </section>
        ) : null}
      </section>

      <section className="panel stack">
        <h2>Settlements</h2>
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Status</th>
              <th>Indexed Features</th>
            </tr>
          </thead>
          <tbody>
            {adminSettlements.map((s) => (
              <tr key={s.id}>
                <td>{s.title}</td>
                <td>{s.status}</td>
                <td>{s.feature_index_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel stack">
        <h2>Recent Events</h2>
        <ul>
          {adminEvents.map((e) => (
            <li key={e.id} className="muted">
              {e.type} {e.user_id ? `(${e.user_id})` : ""}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel stack">
        <h2>ML Feedback</h2>
        <div className="toolbar">
          <button onClick={loadDataset} disabled={mlLoading}>
            {mlLoading ? "Loading..." : "Load Dataset"}
          </button>
          <button onClick={exportLabeled} disabled={mlLoading} className="ghost-btn">
            Export & Label
          </button>
        </div>
        {mlSamples !== null && (
          <>
            <div className="ml-stats-grid">
              <article className="stat-card">
                <h3>Total</h3>
                <p>{mlCount}</p>
              </article>
              <article className="stat-card">
                <h3>Pending</h3>
                <p>{mlSamples.filter(s => s.label === null).length}</p>
              </article>
              <article className="stat-card">
                <h3>Paid Out</h3>
                <p>{mlSamples.filter(s => s.outcome === 'paid_out').length}</p>
              </article>
              <article className="stat-card">
                <h3>Not Paid</h3>
                <p>{mlSamples.filter(s => s.outcome === 'not_paid_out').length}</p>
              </article>
              <article className="stat-card">
                <h3>Ignored</h3>
                <p>{mlSamples.filter(s => s.outcome === 'ignored').length}</p>
              </article>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Settlement</th>
                  <th>Outcome</th>
                  <th>Label</th>
                  <th>Confidence</th>
                  <th>Similarity</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {mlSamples.slice(0, 50).map((s, i) => (
                  <tr key={i}>
                    <td title={s.settlement_id}>{s.settlement_id.slice(0, 8)}…</td>
                    <td>{s.outcome}</td>
                    <td>{s.label === null ? "pending" : s.label === 1 ? "✓ positive" : "negative"}</td>
                    <td>{(s.rules_confidence * 100).toFixed(1)}%</td>
                    <td>{(s.similarity * 100).toFixed(1)}%</td>
                    <td>{new Date(s.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {exportJson && (
              <details>
                <summary className="muted" style={{ cursor: 'pointer' }}>Raw JSON</summary>
                <pre className="json-pre">{exportJson}</pre>
              </details>
            )}
          </>
        )}
      </section>
    </AppShell>
  );
}
