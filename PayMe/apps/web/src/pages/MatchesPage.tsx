import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../api";
import { SettlementCard } from "../components/SettlementCard";

type Match = {
  settlement_id: string;
  title: string;
  score: number;
  pinned: boolean;
  reasons_json: { matched_features?: string[]; confidence_breakdown?: Record<string, number> };
};

export function MatchesPage() {
  const [items, setItems] = useState<Match[]>([]);
  const [syncing, setSyncing] = useState(false);

  const load = async () => {
    const rows = await apiFetch<Match[]>("/match/results");
    setItems(rows);
  };

  useEffect(() => {
    load();
  }, []);

  const syncGmail = async () => {
    setSyncing(true);
    try {
      await apiFetch("/integrations/gmail/sync", { method: "POST" });
      await apiFetch("/match/run", { method: "POST" });
      await load();
    } finally {
      setSyncing(false);
    }
  };

  const syncPlaid = async () => {
    setSyncing(true);
    try {
      await apiFetch("/integrations/plaid/sync", { method: "POST" });
      await apiFetch("/match/run", { method: "POST" });
      await load();
    } finally {
      setSyncing(false);
    }
  };

  return (
    <main>
      <h1>Top Matching Settlements</h1>
      <Link to="/admin">Open Admin Panel</Link>
      <button onClick={syncGmail} disabled={syncing}>{syncing ? "Syncing..." : "Connect Gmail"}</button>
      <button onClick={syncPlaid} disabled={syncing} style={{ marginLeft: 8 }}>
        {syncing ? "Syncing..." : "Connect Bank"}
      </button>
      <section>
        {items.map((item) => (
          <SettlementCard key={item.settlement_id} item={item} onChange={load} />
        ))}
      </section>
    </main>
  );
}
