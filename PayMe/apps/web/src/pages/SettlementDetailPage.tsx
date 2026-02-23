import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiFetch } from "../api";
import { AppShell } from "../components/AppShell";
import { useApp } from "../context/AppContext";
import { SettlementDetail } from "../types";

export function SettlementDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { beginClaimFlow } = useApp();
  const [detail, setDetail] = useState<SettlementDetail | null>(null);
  const [error, setError] = useState("");
  const claimStatusLabel = detail?.claim_status?.replace("_", " ") || "submitted";

  useEffect(() => {
    apiFetch<SettlementDetail>(`/settlements/${id}`).then(setDetail).catch((err) => setError((err as Error).message));
  }, [id]);

  if (!detail) return <div className="loader">{error || "Loading settlement..."}</div>;
  return (
    <AppShell title={detail.title} subtitle={`Status: ${detail.status}`}>
      <article className="detail-card stack">
        <div>
          <button className="ghost-btn" onClick={() => navigate("/")}>
            Back to Matches
          </button>
        </div>
        <p>{detail.summary_text}</p>
        <p className="muted">{detail.eligibility_text}</p>
        <p className="muted">
          States: {detail.states?.length ? detail.states.join(", ") : "All"}
        </p>
        <p className="muted">
          Deadline: {detail.deadline ? new Date(detail.deadline).toLocaleDateString() : "Not specified"}
        </p>
        {detail.claim_submitted_at ? (
          <section className="claim-history-card">
            <div className="claim-history-head">
              <p className="claim-history-title">Claim Progress</p>
              <span className={`status-pill status-${detail.claim_status || "submitted"}`}>{claimStatusLabel}</span>
            </div>
            <div className="claim-history-grid">
              <p className="claim-meta-label">Submitted</p>
              <p>{new Date(detail.claim_submitted_at).toLocaleDateString()}</p>
              <p className="claim-meta-label">Outcome Recorded</p>
              <p>{detail.claim_outcome_at ? new Date(detail.claim_outcome_at).toLocaleDateString() : "Pending"}</p>
            </div>
          </section>
        ) : null}
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
          <button
            onClick={() =>
              beginClaimFlow({
                settlementId: detail.id,
                title: detail.title,
                claimUrl: detail.claim_url,
              })
            }
          >
            Open Claim Form
          </button>
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
