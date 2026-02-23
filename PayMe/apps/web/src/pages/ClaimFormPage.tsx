import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiFetch } from "../api";
import type { SettlementQuestion, ClaimEvidence, ClaimSubmitResult } from "../types";

type Step = 1 | 2 | 3;

const STEP_LABELS = ["Questions", "Evidence", "Result"] as const;

export function ClaimFormPage() {
  const { settlementId } = useParams<{ settlementId: string }>();
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>(1);
  const [settlementTitle, setSettlementTitle] = useState("");
  const [questions, setQuestions] = useState<SettlementQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState("");

  const [evidence, setEvidence] = useState<ClaimEvidence | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [gmailChecked, setGmailChecked] = useState<Record<string, boolean>>({});
  const [plaidChecked, setPlaidChecked] = useState<Record<string, boolean>>({});
  const [gmailOpen, setGmailOpen] = useState(true);
  const [plaidOpen, setPlaidOpen] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [result, setResult] = useState<ClaimSubmitResult | null>(null);

  // Load settlement + questions on mount
  useEffect(() => {
    if (!settlementId) return;
    Promise.all([
      apiFetch<{ title: string }>(`/settlements/${settlementId}`).then((s) =>
        setSettlementTitle(s.title)
      ),
      apiFetch<SettlementQuestion[]>(`/settlements/${settlementId}/questions`).then(
        (qs) => setQuestions(qs.sort((a, b) => a.order_index - b.order_index))
      ),
    ]).catch(() => setLoadError("Failed to load questions."));
  }, [settlementId]);

  const setAnswer = (questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
    setValidationErrors((prev) => {
      const next = { ...prev };
      delete next[questionId];
      return next;
    });
  };

  const validateStep1 = (): boolean => {
    const errors: Record<string, string> = {};
    for (const q of questions) {
      if (q.required && !answers[q.id]?.trim()) {
        errors[q.id] = "This field is required.";
      }
    }
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const advanceToStep2 = async () => {
    if (!validateStep1()) return;
    // Fire-and-forget claim opened event
    apiFetch(`/settlements/${settlementId}/claim/opened`, { method: "POST" }).catch(
      () => {}
    );
    // Load evidence
    setEvidenceLoading(true);
    try {
      const ev = await apiFetch<ClaimEvidence>(
        `/settlements/${settlementId}/evidence`
      );
      setEvidence(ev);
      const gChecked: Record<string, boolean> = {};
      for (const g of ev.gmail) gChecked[g.id] = true;
      setGmailChecked(gChecked);
      const pChecked: Record<string, boolean> = {};
      for (const p of ev.plaid) pChecked[p.id] = true;
      setPlaidChecked(pChecked);
    } catch {
      setEvidence({ gmail: [], plaid: [] });
    } finally {
      setEvidenceLoading(false);
    }
    setStep(2);
  };

  const submitClaim = async () => {
    setSubmitting(true);
    setSubmitError("");
    try {
      const gmail_evidence_ids = Object.entries(gmailChecked)
        .filter(([, v]) => v)
        .map(([k]) => k);
      const plaid_evidence_ids = Object.entries(plaidChecked)
        .filter(([, v]) => v)
        .map(([k]) => k);
      const answersArray = Object.entries(answers).map(([question_id, value]) => ({
        question_id,
        value,
      }));
      const res = await apiFetch<ClaimSubmitResult>(
        `/settlements/${settlementId}/submit`,
        {
          method: "POST",
          body: JSON.stringify({ answers: answersArray, gmail_evidence_ids, plaid_evidence_ids }),
        }
      );
      setResult(res);
      setStep(3);
    } catch (err) {
      setSubmitError((err as Error).message || "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const fmtDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString();
    } catch {
      return iso;
    }
  };

  const fmtDollars = (cents: number) =>
    `$${(cents / 100).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;

  // --- Render helpers ---

  const renderStepIndicator = () => (
    <div className="wizard-steps">
      {STEP_LABELS.map((label, i) => {
        const num = (i + 1) as Step;
        const cls =
          num === step ? "wizard-step active" : num < step ? "wizard-step done" : "wizard-step";
        return (
          <div key={num} style={{ display: "contents" }}>
            {i > 0 && <div className="wizard-connector" />}
            <div className={cls}>
              <div className="wizard-step-dot">{num}</div>
              <span className="wizard-step-label">{label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );

  const renderQuestion = (q: SettlementQuestion) => {
    const val = answers[q.id] || "";
    const err = validationErrors[q.id];

    let input: React.ReactNode;
    switch (q.question_type) {
      case "yes_no":
        input = (
          <div style={{ display: "flex", gap: "1rem" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <input
                type="radio"
                name={q.id}
                value="Yes"
                checked={val === "Yes"}
                onChange={() => setAnswer(q.id, "Yes")}
              />
              Yes
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <input
                type="radio"
                name={q.id}
                value="No"
                checked={val === "No"}
                onChange={() => setAnswer(q.id, "No")}
              />
              No
            </label>
          </div>
        );
        break;
      case "date":
        input = (
          <input
            type="date"
            value={val}
            onChange={(e) => setAnswer(q.id, e.target.value)}
          />
        );
        break;
      case "amount":
        input = (
          <input
            type="number"
            min="0"
            step="0.01"
            value={val}
            onChange={(e) => setAnswer(q.id, e.target.value)}
            placeholder="0.00"
          />
        );
        break;
      case "select":
        input = (
          <select value={val} onChange={(e) => setAnswer(q.id, e.target.value)}>
            <option value="">-- Select --</option>
            {(q.options_json || []).map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        );
        break;
      default:
        input = (
          <input
            type="text"
            value={val}
            onChange={(e) => setAnswer(q.id, e.target.value)}
            placeholder="Your answer"
          />
        );
    }

    return (
      <div key={q.id} style={{ marginBottom: "1rem" }}>
        <label style={{ display: "block", marginBottom: "0.4rem", fontWeight: 500 }}>
          {q.question_text}
          {q.required && <span style={{ color: "var(--danger)", marginLeft: "0.25rem" }}>*</span>}
        </label>
        {input}
        {err && <p className="error" style={{ margin: "0.3rem 0 0", fontSize: "0.82rem" }}>{err}</p>}
      </div>
    );
  };

  const renderStep1 = () => (
    <div>
      {loadError ? (
        <p className="error">{loadError}</p>
      ) : questions.length === 0 ? (
        <p className="muted">Loading questions...</p>
      ) : (
        <>
          {questions.map(renderQuestion)}
          <button onClick={advanceToStep2} style={{ marginTop: "0.5rem" }}>
            Next: Review Evidence &rarr;
          </button>
        </>
      )}
    </div>
  );

  const renderStep2 = () => {
    if (evidenceLoading) return <p className="muted">Loading evidence...</p>;
    const hasGmail = evidence && evidence.gmail.length > 0;
    const hasPlaid = evidence && evidence.plaid.length > 0;
    const hasAny = hasGmail || hasPlaid;

    return (
      <div>
        <button
          className="ghost-btn"
          onClick={() => setStep(1)}
          style={{ marginBottom: "1rem", fontSize: "0.85rem" }}
        >
          &larr; Back to Questions
        </button>

        {!hasAny && (
          <p className="muted" style={{ marginBottom: "1rem" }}>
            No matching evidence found — you can still submit your claim.
          </p>
        )}

        {hasGmail && (
          <div style={{ marginBottom: "1rem" }}>
            <button
              className="ghost-btn"
              onClick={() => setGmailOpen((o) => !o)}
              style={{ width: "100%", textAlign: "left", fontWeight: 700 }}
            >
              {gmailOpen ? "\u25BE" : "\u25B8"} Email Receipts ({evidence!.gmail.length})
            </button>
            {gmailOpen && (
              <div style={{ marginTop: "0.5rem" }}>
                {evidence!.gmail.map((g) => (
                  <label
                    key={g.id}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "0.6rem",
                      padding: "0.6rem 0",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={gmailChecked[g.id] ?? false}
                      onChange={(e) =>
                        setGmailChecked((prev) => ({ ...prev, [g.id]: e.target.checked }))
                      }
                      style={{ marginTop: "0.2rem", width: "auto" }}
                    />
                    <div>
                      <p style={{ margin: 0, fontWeight: 500 }}>{g.subject}</p>
                      <p className="muted" style={{ margin: "0.15rem 0 0", fontSize: "0.82rem" }}>
                        {g.from_domain} &middot; {fmtDate(g.internal_date)}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {hasPlaid && (
          <div style={{ marginBottom: "1rem" }}>
            <button
              className="ghost-btn"
              onClick={() => setPlaidOpen((o) => !o)}
              style={{ width: "100%", textAlign: "left", fontWeight: 700 }}
            >
              {plaidOpen ? "\u25BE" : "\u25B8"} Bank Transactions ({evidence!.plaid.length})
            </button>
            {plaidOpen && (
              <div style={{ marginTop: "0.5rem" }}>
                {evidence!.plaid.map((p) => (
                  <label
                    key={p.id}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "0.6rem",
                      padding: "0.6rem 0",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={plaidChecked[p.id] ?? false}
                      onChange={(e) =>
                        setPlaidChecked((prev) => ({ ...prev, [p.id]: e.target.checked }))
                      }
                      style={{ marginTop: "0.2rem", width: "auto" }}
                    />
                    <div>
                      <p style={{ margin: 0, fontWeight: 500 }}>{p.merchant_name}</p>
                      <p className="muted" style={{ margin: "0.15rem 0 0", fontSize: "0.82rem" }}>
                        {fmtDollars(p.amount_cents)} &middot; {fmtDate(p.posted_at)}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {submitError && <p className="error" style={{ marginBottom: "0.5rem" }}>{submitError}</p>}

        <button onClick={submitClaim} disabled={submitting} style={{ marginTop: "0.5rem" }}>
          {submitting ? "Submitting..." : "Submit Claim \u2192"}
        </button>
      </div>
    );
  };

  const renderStep3 = () => {
    if (!result) return null;

    return (
      <div>
        {result.auto_approved ? (
          <div
            style={{
              background: "rgba(133, 255, 158, 0.12)",
              border: "1px solid rgba(133, 255, 158, 0.5)",
              borderRadius: "12px",
              padding: "1rem",
              marginBottom: "1rem",
            }}
          >
            <p style={{ margin: 0, fontWeight: 700, color: "var(--accent-2)" }}>
              Your claim was automatically approved!
            </p>
            {result.amount_cents != null && (
              <p style={{ margin: "0.4rem 0 0", color: "var(--accent-2)" }}>
                Payment of {fmtDollars(result.amount_cents)} is processing.
              </p>
            )}
          </div>
        ) : (
          <div
            style={{
              background: "rgba(104, 225, 253, 0.1)",
              border: "1px solid rgba(104, 225, 253, 0.4)",
              borderRadius: "12px",
              padding: "1rem",
              marginBottom: "1rem",
            }}
          >
            <p style={{ margin: 0, fontWeight: 700, color: "var(--accent)" }}>
              Your claim has been submitted and is pending review.
            </p>
          </div>
        )}

        <button onClick={() => navigate("/")}>Back to Matches</button>
      </div>
    );
  };

  return (
    <div className="page" style={{ maxWidth: "680px", margin: "0 auto", padding: "1.5rem 1rem" }}>
      <h2 style={{ fontFamily: "'Fraunces', serif", marginBottom: "0.3rem" }}>
        {settlementTitle || "Claim Form"}
      </h2>
      {renderStepIndicator()}
      <div className="panel" style={{ padding: "1.25rem" }}>
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
      </div>
    </div>
  );
}
