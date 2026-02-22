import { apiFetch } from "../api";
import { MatchReasonSummary } from "./MatchReasonSummary";
import { Link } from "react-router-dom";

type Match = {
  settlement_id: string;
  title: string;
  score: number;
  pinned: boolean;
  reasons_json: { matched_features?: string[]; confidence_breakdown?: Record<string, number> };
};

type Props = {
  item: Match;
  onChange: () => Promise<void>;
};

export function SettlementCard({ item, onChange }: Props) {
  const togglePin = async () => {
    const method = item.pinned ? "DELETE" : "POST";
    await apiFetch(`/settlements/${item.settlement_id}/pin`, { method });
    await onChange();
  };

  return (
    <article style={{ border: "1px solid #ddd", marginBottom: 12, padding: 12, borderRadius: 8 }}>
      <h3>{item.pinned ? "📌 " : ""}{item.title}</h3>
      <Link to={`/settlements/${item.settlement_id}`}>View details</Link>
      <p>Score: {item.score.toFixed(2)}</p>
      <MatchReasonSummary reasons={item.reasons_json} />
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button onClick={togglePin}>{item.pinned ? "Unpin" : "Pin"}</button>
      </div>
    </article>
  );
}
