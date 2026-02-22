import { useEffect, useState } from "react";
import { AppShell } from "../components/AppShell";
import { useApp } from "../context/AppContext";

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
    </AppShell>
  );
}
