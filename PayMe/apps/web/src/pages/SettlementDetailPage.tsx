import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch } from "../api";
import { AppShell } from "../components/AppShell";
import { SettlementDetail } from "../types";

export function SettlementDetailPage() {
  const { id } = useParams();
  const [detail, setDetail] = useState<SettlementDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<SettlementDetail>(`/settlements/${id}`).then(setDetail).catch((err) => setError((err as Error).message));
  }, [id]);

  if (!detail) return <div className="loader">{error || "Loading settlement..."}</div>;
  return (
    <AppShell title={detail.title} subtitle={`Status: ${detail.status}`}>
      <article className="detail-card stack">
        <p>{detail.summary_text}</p>
        <p className="muted">{detail.eligibility_text}</p>
        <p className="muted">
          States: {detail.states?.length ? detail.states.join(", ") : "All"}
        </p>
        <p className="muted">
          Deadline: {detail.deadline ? new Date(detail.deadline).toLocaleDateString() : "Not specified"}
        </p>
        {(detail.payout_min_cents ?? detail.payout_max_cents) !== undefined ? (
          <p className="muted">
            Payout:{" "}
            {detail.payout_min_cents != null
              ? `$${(detail.payout_min_cents / 100).toLocaleString()}`
              : "$0"}
            {" - "}
            {detail.payout_max_cents != null
              ? `$${(detail.payout_max_cents / 100).toLocaleString()}`
              : "Unknown"}
          </p>
        ) : null}
        <div className="toolbar">
          <a href={detail.claim_url} target="_blank" rel="noreferrer">
            <button>Open Claim Form</button>
          </a>
          {detail.website_url ? (
            <a href={detail.website_url} target="_blank" rel="noreferrer">
              <button className="ghost-btn">Settlement Website</button>
            </a>
          ) : null}
        </div>
      </article>
    </AppShell>
  );
}
