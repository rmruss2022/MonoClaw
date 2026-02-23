import { useState } from "react";
import { apiFetch } from "../api";
import { Link } from "react-router-dom";
import { useApp } from "../context/AppContext";
import { Match } from "../types";

type Props = {
  item: Match;
  onChange: () => Promise<void>;
};

export function SettlementCard({ item, onChange }: Props) {
  const { beginClaimFlow, enqueueAutofillJob } = useApp();
  const [autofillQueued, setAutofillQueued] = useState(false);
  const [autofillMsg, setAutofillMsg] = useState("");
  const scoreValue = Math.round(item.score * 100);
  const scorePercent = `${scoreValue}%`;
  const accuracyClass = scoreValue > 80 ? "accuracy-high" : "accuracy-mid";
  const payout = (() => {
    const min = item.payout_min_cents ?? null;
    const max = item.payout_max_cents ?? null;
    if (min === null && max === null) return "Unknown";
    const toUsd = (cents: number) => `$${(cents / 100).toLocaleString()}`;
    if (min !== null && max !== null) return `${toUsd(min)} - ${toUsd(max)}`;
    if (min !== null) return `${toUsd(min)}+`;
    return `Up to ${toUsd(max as number)}`;
  })();

  const togglePin = async () => {
    const method = item.pinned ? "DELETE" : "POST";
    await apiFetch(`/settlements/${item.settlement_id}/pin`, { method });
    await onChange();
  };

  const handleAutofill = async () => {
    try {
      await enqueueAutofillJob(item.settlement_id);
      setAutofillQueued(true);
      setAutofillMsg("Autofill job queued!");
    } catch (err) {
      setAutofillMsg((err as Error).message || "Failed to queue autofill");
    }
  };

  const deadlineText = item.deadline ? new Date(item.deadline).toLocaleDateString() : "Not specified";

  return (
    <article className="match-card">
      <div className="row">
        <h3>{item.pinned ? "📌 " : ""}{item.title}</h3>
        <button className="ghost-btn pin-btn" onClick={togglePin}>
          {item.pinned ? "Unpin" : "Pin"}
        </button>
      </div>
      <p className={`accuracy-line ${accuracyClass}`}>Accuracy: {scorePercent}</p>
      {item.claim_status ? <p className="claim-status">Claim status: {item.claim_status.replace("_", " ")}</p> : null}
      {item.summary_text ? <p className="muted">{item.summary_text}</p> : null}
      <p className="muted">Estimated payout: {payout}</p>
      <p className="muted">Deadline: {deadlineText}</p>
      {item.states?.length ? <p className="muted">States: {item.states.join(", ")}</p> : <p className="muted">States: All</p>}
      <div className="toolbar action-stack">
        <Link to={`/settlements/${item.settlement_id}`}>
          <button className="ghost-btn">View details</button>
        </Link>
        {item.claim_url ? (
          <button
            className="claim-btn"
            onClick={() =>
              beginClaimFlow({ settlementId: item.settlement_id, title: item.title, claimUrl: item.claim_url || null })
            }
          >
            Open Claim Form
          </button>
        ) : null}
        <button
          className="ghost-btn"
          onClick={handleAutofill}
          disabled={autofillQueued}
          style={{ fontSize: '0.85rem' }}
        >
          {autofillQueued ? "Autofill Queued ✓" : "Start Autofill"}
        </button>
        {autofillMsg ? <p className="muted" style={{ fontSize: '0.8rem', margin: '0.25rem 0 0' }}>{autofillMsg}</p> : null}
      </div>
    </article>
  );
}
