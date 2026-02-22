import { useEffect, useState } from "react";
import { apiFetch } from "../api";

type Overview = Record<string, number>;
type AdminUser = {
  id: string;
  username: string;
  email: string;
  state: string | null;
  match_count: number;
};
type AdminSettlement = {
  id: string;
  title: string;
  status: string;
  feature_index_count: number;
};
type UserStats = {
  user_id: string;
  total_match_results: number;
  latest_run_id: string | null;
  latest_run_result_count: number;
  average_score: number;
  gmail_messages: number;
  plaid_transactions: number;
};

export function AdminPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [settlements, setSettlements] = useState<AdminSettlement[]>([]);
  const [events, setEvents] = useState<Array<{ id: string; type: string; user_id: string | null }>>([]);
  const [selectedUser, setSelectedUser] = useState<string>("");
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try {
      const [overviewData, usersData, settlementsData, eventsData] = await Promise.all([
        apiFetch<Overview>("/admin/stats/overview"),
        apiFetch<AdminUser[]>("/admin/users?limit=100"),
        apiFetch<AdminSettlement[]>("/admin/settlements?limit=100"),
        apiFetch<Array<{ id: string; type: string; user_id: string | null }>>("/admin/events?limit=30"),
      ]);
      setOverview(overviewData);
      setUsers(usersData);
      setSettlements(settlementsData);
      setEvents(eventsData);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const loadUserStats = async () => {
    if (!selectedUser) return;
    const stats = await apiFetch<UserStats>(`/admin/stats/users/${selectedUser}`);
    setUserStats(stats);
  };

  return (
    <main>
      <h1>Admin Debug Panel</h1>
      <button onClick={load}>Refresh</button>
      {error && <p>{error}. Ensure ADMIN_DEBUG=true.</p>}

      <section>
        <h2>Overview</h2>
        <pre>{JSON.stringify(overview, null, 2)}</pre>
      </section>

      <section>
        <h2>Users</h2>
        <table>
          <thead>
            <tr><th>Username</th><th>Email</th><th>State</th><th>Matches</th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.email}</td>
                <td>{u.state || "-"}</td>
                <td>{u.match_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ marginTop: 12 }}>
          <select value={selectedUser} onChange={(e) => setSelectedUser(e.target.value)}>
            <option value="">Select user for stats</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
          </select>
          <button onClick={loadUserStats} style={{ marginLeft: 8 }}>Load user stats</button>
          {userStats && <pre>{JSON.stringify(userStats, null, 2)}</pre>}
        </div>
      </section>

      <section>
        <h2>Settlements</h2>
        <table>
          <thead>
            <tr><th>Title</th><th>Status</th><th>Indexed Features</th></tr>
          </thead>
          <tbody>
            {settlements.map((s) => (
              <tr key={s.id}>
                <td>{s.title}</td>
                <td>{s.status}</td>
                <td>{s.feature_index_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Recent Events</h2>
        <ul>
          {events.map((e) => <li key={e.id}>{e.type} {e.user_id ? `(${e.user_id})` : ""}</li>)}
        </ul>
      </section>
    </main>
  );
}
