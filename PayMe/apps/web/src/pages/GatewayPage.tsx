import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api";
import { AppShell } from "../components/AppShell";
import { useApp } from "../context/AppContext";
import type { PayoutHistoryItem, PayoutQueueItem, SettlementQuestion } from "../types";

type AttorneyInfo = {
  attorney_id: string;
  name: string;
  email: string;
  firm_name: string | null;
};

type BalanceInfo = {
  bank_name: string;
  sandbox_balance_cents: number;
  disbursed_cents: number;
  pending_approval_cents: number;
  available_cents: number;
};

const STATUS_COLORS: Record<string, string> = {
  pending: "var(--muted)",
  approved: "#ffd166",
  paid: "var(--accent-2)",
  rejected: "var(--danger)",
  failed: "var(--danger)",
  completed: "var(--accent-2)",
  processing: "#ffd166",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "0.2rem 0.5rem",
        borderRadius: "999px",
        fontSize: "0.75rem",
        fontWeight: 700,
        background: `${STATUS_COLORS[status] ?? "var(--border)"}22`,
        color: STATUS_COLORS[status] ?? "var(--muted)",
        border: `1px solid ${STATUS_COLORS[status] ?? "var(--border)"}55`,
        whiteSpace: "nowrap",
      }}
    >
      {status}
    </span>
  );
}

function tabBtn(active: boolean) {
  return {
    padding: "0.5rem 1.1rem",
    background: active ? "var(--accent)" : "var(--bg-soft)",
    color: active ? "#07090f" : "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    cursor: "pointer",
    fontWeight: active ? 700 : 400,
  } as React.CSSProperties;
}

export function GatewayPage() {
  const { user, isAuthenticated, authStatus } = useApp();
  const navigate = useNavigate();
  const [attorney, setAttorney] = useState<AttorneyInfo | null>(null);
  const [balance, setBalance] = useState<BalanceInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"queue" | "history" | "questions">("queue");

  const refreshBalance = useCallback(() => {
    apiFetch<BalanceInfo>("/gateway/account/balance")
      .then(setBalance)
      .catch(() => {/* non-fatal */});
  }, []);

  useEffect(() => {
    if (authStatus === "booting") return;
    if (!isAuthenticated) {
      navigate("/login");
      return;
    }
    const role = user?.role;
    if (!role || !["attorney", "admin", "super_user"].includes(role)) {
      setError("You don't have permission to access the Gateway. Contact an admin.");
      setLoading(false);
      return;
    }
    Promise.all([
      apiFetch<AttorneyInfo>("/gateway/me"),
      apiFetch<BalanceInfo>("/gateway/account/balance"),
    ])
      .then(([atty, bal]) => { setAttorney(atty); setBalance(bal); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [authStatus, isAuthenticated, user]);

  if (loading) {
    return (
      <AppShell title="PayMe Gateway" subtitle="Settlement payout management">
        <p className="muted">Loading gateway...</p>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell title="PayMe Gateway" subtitle="Settlement payout management">
        <div className="panel">
          <p className="error">{error}</p>
          {!isAuthenticated && <button onClick={() => navigate("/login")}>Log in</button>}
        </div>
      </AppShell>
    );
  }

  if (!attorney) return null;

  return (
    <AppShell
      title="PayMe Gateway"
      subtitle={`${attorney.name}${attorney.firm_name ? ` · ${attorney.firm_name}` : ""}`}
    >
      <div style={{ maxWidth: 1040, margin: "0 auto" }}>
        {balance && <BalanceCard balance={balance} />}

        <div style={{ display: "flex", gap: "0.5rem", margin: "1rem 0" }}>
          <button style={tabBtn(tab === "queue")} onClick={() => setTab("queue")}>
            Payout Queue
          </button>
          <button style={tabBtn(tab === "history")} onClick={() => setTab("history")}>
            History
          </button>
          <button style={tabBtn(tab === "questions")} onClick={() => setTab("questions")}>
            Settlement Questions
          </button>
        </div>

        {tab === "queue" && <QueueTab attorney={attorney} onPayoutComplete={refreshBalance} />}
        {tab === "history" && <HistoryTab attorney={attorney} />}
        {tab === "questions" && <QuestionsTab />}
      </div>
    </AppShell>
  );
}

/* ---- Balance Card ---- */

function fmt(cents: number) {
  return `$${(cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function BalanceCard({ balance }: { balance: BalanceInfo }) {
  const stats = [
    { label: "Available", value: fmt(balance.available_cents), color: "var(--accent-2)" },
    { label: "Disbursed", value: fmt(balance.disbursed_cents), color: "var(--muted)" },
    { label: "Pending Approvals", value: fmt(balance.pending_approval_cents), color: "#ffd166" },
  ];
  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: "1rem 1.25rem",
        marginBottom: "0.5rem",
        display: "flex",
        gap: "1.5rem",
        alignItems: "center",
        flexWrap: "wrap",
      }}
    >
      <div>
        <div className="muted" style={{ fontSize: "0.72rem", marginBottom: 2 }}>
          SETTLEMENT FUND
        </div>
        <div style={{ fontWeight: 700, fontSize: "0.92rem" }}>{balance.bank_name}</div>
        <div className="muted" style={{ fontSize: "0.72rem" }}>
          Sandbox · {fmt(balance.sandbox_balance_cents)} limit
        </div>
      </div>
      <div
        style={{
          display: "flex",
          gap: "1.5rem",
          flexWrap: "wrap",
          marginLeft: "auto",
        }}
      >
        {stats.map((s) => (
          <div key={s.label} style={{ textAlign: "right" }}>
            <div style={{ fontSize: "1.15rem", fontWeight: 700, color: s.color }}>
              {s.value}
            </div>
            <div className="muted" style={{ fontSize: "0.72rem" }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---- Queue Tab ---- */

type RowState = { amount: string };

const ALL_STATUSES = ["all", "pending", "approved", "paid", "rejected", "failed"] as const;
type StatusFilter = (typeof ALL_STATUSES)[number];

function QueueTab({ attorney, onPayoutComplete }: { attorney: AttorneyInfo; onPayoutComplete: () => void }) {
  const [queue, setQueue] = useState<PayoutQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [rowState, setRowState] = useState<Record<string, RowState>>({});
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [paying, setPaying] = useState(false);
  const [payResult, setPayResult] = useState<string>("");

  const rowKey = (item: PayoutQueueItem) => `${item.user_id}:${item.settlement_id}`;

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<PayoutQueueItem[]>("/gateway/payouts/queue");
      setQueue(data);
      // Pre-fill amounts from settlement default or existing approval
      const init: Record<string, RowState> = {};
      for (const item of data) {
        const key = `${item.user_id}:${item.settlement_id}`;
        const defaultAmt =
          item.approved_amount_cents != null
            ? String(item.approved_amount_cents)
            : String(item.settlement_payout_min_cents ?? "");
        init[key] = { amount: defaultAmt };
      }
      setRowState(init);
    } catch (e: unknown) {
      setError((e as Error).message || "Failed to load queue");
    } finally {
      setLoading(false);
    }
  }, [attorney]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const filtered = queue.filter(
    (item) => statusFilter === "all" || item.approval_status === statusFilter,
  );

  const payableStatuses = new Set(["pending", "approved"]);
  const payable = filtered.filter((item) => payableStatuses.has(item.approval_status));

  const toggleSelect = (key: string) =>
    setSelected((s) => {
      const next = new Set(s);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const toggleSelectAll = () => {
    const payableKeys = payable.map(rowKey);
    const allSelected = payableKeys.every((k) => selected.has(k));
    if (allSelected) {
      setSelected((s) => {
        const next = new Set(s);
        payableKeys.forEach((k) => next.delete(k));
        return next;
      });
    } else {
      setSelected((s) => new Set([...s, ...payableKeys]));
    }
  };

  const setAmount = (key: string, amt: string) =>
    setRowState((rs) => ({ ...rs, [key]: { ...rs[key], amount: amt } }));

  async function paySelected() {
    const items = [...selected]
      .map((key) => {
        const item = queue.find((q) => rowKey(q) === key);
        if (!item) return null;
        const amt = rowState[key]?.amount;
        return {
          user_id: item.user_id,
          settlement_id: item.settlement_id,
          amount_cents: amt ? parseInt(amt, 10) : null,
        };
      })
      .filter(Boolean);

    if (!items.length) return;
    setPaying(true);
    setPayResult("");
    try {
      const result = await apiFetch<{
        batches: Array<{ successful: number; failed: number; total_amount_cents: number }>;
        total_approved: number;
      }>("/gateway/payouts/execute", {
        method: "POST",
        body: JSON.stringify({ items, idempotency_key: crypto.randomUUID() }),
      });
      const successful = result.batches.reduce((s, b) => s + b.successful, 0);
      const failed = result.batches.reduce((s, b) => s + b.failed, 0);
      const totalCents = result.batches.reduce((s, b) => s + b.total_amount_cents, 0);
      setPayResult(
        `Processed ${result.total_approved} claimants — ✓ ${successful} paid ($${(totalCents / 100).toFixed(2)}), ✗ ${failed} failed`,
      );
      setSelected(new Set());
      await loadQueue();
      onPayoutComplete();
    } catch (e: unknown) {
      setPayResult(`Error: ${(e as Error).message}`);
    } finally {
      setPaying(false);
    }
  }

  async function rejectOne(item: PayoutQueueItem) {
    try {
      await apiFetch(
        `/gateway/attorneys/${attorney.attorney_id}/reject/${item.settlement_id}/${item.user_id}`,
        { method: "POST", body: JSON.stringify({ note: null }) },
      );
      await loadQueue();
    } catch (e: unknown) {
      alert((e as Error).message || "Reject failed");
    }
  }

  const payableAllSelected =
    payable.length > 0 && payable.every((item) => selected.has(rowKey(item)));

  const selectedPayableCount = [...selected].filter((k) => {
    const item = queue.find((q) => rowKey(q) === k);
    return item && payableStatuses.has(item.approval_status);
  }).length;

  if (loading) return <p className="muted">Loading queue...</p>;
  if (error) return <p className="error">{error}</p>;

  return (
    <div className="panel stack">
      <div
        style={{
          display: "flex",
          gap: "0.75rem",
          alignItems: "center",
          flexWrap: "wrap",
          marginBottom: "0.5rem",
        }}
      >
        <strong style={{ fontSize: "1rem" }}>
          {queue.length} submitted claim{queue.length !== 1 ? "s" : ""}
        </strong>
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
          {ALL_STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              style={{
                padding: "0.25rem 0.65rem",
                fontSize: "0.78rem",
                background: statusFilter === s ? "var(--accent)" : "var(--bg-soft)",
                color: statusFilter === s ? "#07090f" : "var(--text)",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                cursor: "pointer",
                fontWeight: statusFilter === s ? 700 : 400,
              }}
            >
              {s === "all" ? `All (${queue.length})` : `${s} (${queue.filter((q) => q.approval_status === s).length})`}
            </button>
          ))}
        </div>
        <button
          onClick={loadQueue}
          style={{
            marginLeft: "auto",
            padding: "0.3rem 0.7rem",
            fontSize: "0.8rem",
            background: "var(--bg-soft)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            cursor: "pointer",
            color: "var(--text)",
          }}
        >
          ↻ Refresh
        </button>
      </div>

      {filtered.length === 0 ? (
        <p className="muted">No claimants match this filter.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.85rem",
            }}
          >
            <thead>
              <tr style={{ borderBottom: "2px solid var(--border)", textAlign: "left" }}>
                <th style={{ padding: "0.5rem 0.4rem", width: 32 }}>
                  {payable.length > 0 && (
                    <input
                      type="checkbox"
                      checked={payableAllSelected}
                      onChange={toggleSelectAll}
                      title="Select all payable rows"
                    />
                  )}
                </th>
                <th style={{ padding: "0.5rem 0.4rem" }}>Settlement</th>
                <th style={{ padding: "0.5rem 0.4rem" }}>User</th>
                <th style={{ padding: "0.5rem 0.4rem", whiteSpace: "nowrap" }}>Submitted</th>
                <th style={{ padding: "0.5rem 0.4rem" }}>Status</th>
                <th style={{ padding: "0.5rem 0.4rem", whiteSpace: "nowrap" }}>
                  Amount (¢)
                </th>
                <th style={{ padding: "0.5rem 0.4rem" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const key = rowKey(item);
                const isPayable = payableStatuses.has(item.approval_status);
                const isSelected = selected.has(key);
                return (
                  <tr
                    key={key}
                    style={{
                      borderBottom: "1px solid var(--border)",
                      opacity: !isPayable ? 0.6 : 1,
                      background: isSelected ? "rgba(133,255,158,0.05)" : undefined,
                    }}
                  >
                    <td style={{ padding: "0.45rem 0.4rem" }}>
                      {isPayable && (
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(key)}
                        />
                      )}
                    </td>
                    <td style={{ padding: "0.45rem 0.4rem", maxWidth: 180 }}>
                      <span
                        style={{
                          display: "block",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={item.settlement_title}
                      >
                        {item.settlement_title}
                      </span>
                    </td>
                    <td style={{ padding: "0.45rem 0.4rem" }}>
                      <div>{item.email}</div>
                      {(item.first_name || item.last_name) && (
                        <div className="muted" style={{ fontSize: "0.78rem" }}>
                          {[item.first_name, item.last_name].filter(Boolean).join(" ")}
                        </div>
                      )}
                    </td>
                    <td
                      className="muted"
                      style={{ padding: "0.45rem 0.4rem", whiteSpace: "nowrap", fontSize: "0.78rem" }}
                    >
                      {new Date(item.submitted_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: "0.45rem 0.4rem" }}>
                      <StatusBadge status={item.approval_status} />
                    </td>
                    <td style={{ padding: "0.45rem 0.4rem" }}>
                      {isPayable && (
                        <input
                          type="number"
                          min={0}
                          value={rowState[key]?.amount ?? ""}
                          onChange={(e) => setAmount(key, e.target.value)}
                          style={{ width: 90, fontSize: "0.82rem" }}
                          placeholder="cents"
                        />
                      )}
                      {!isPayable && item.approved_amount_cents != null && (
                        <span className="muted" style={{ fontSize: "0.82rem" }}>
                          ${(item.approved_amount_cents / 100).toFixed(2)}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "0.45rem 0.4rem" }}>
                      {isPayable && (
                        <button
                          onClick={() => rejectOne(item)}
                          style={{
                            padding: "0.2rem 0.55rem",
                            fontSize: "0.78rem",
                            background: "transparent",
                            border: "1px solid var(--danger)",
                            color: "var(--danger)",
                            borderRadius: "4px",
                            cursor: "pointer",
                          }}
                        >
                          Reject
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Bulk action bar */}
      <div
        style={{
          display: "flex",
          gap: "0.75rem",
          alignItems: "center",
          padding: "0.75rem 0",
          borderTop: "1px solid var(--border)",
          flexWrap: "wrap",
        }}
      >
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          {selectedPayableCount > 0 ? `${selectedPayableCount} selected` : "Select rows to pay"}
        </span>
        <button
          onClick={paySelected}
          disabled={paying || selectedPayableCount === 0}
          style={{
            padding: "0.45rem 1rem",
            background: selectedPayableCount > 0 ? "var(--accent)" : "var(--bg-soft)",
            color: selectedPayableCount > 0 ? "#07090f" : "var(--muted)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            cursor: selectedPayableCount > 0 ? "pointer" : "not-allowed",
            fontWeight: 700,
          }}
        >
          {paying ? "Processing..." : `Pay & Approve Selected (${selectedPayableCount})`}
        </button>
        {payable.length > 0 && (
          <button
            onClick={() => {
              setSelected(new Set(payable.map(rowKey)));
            }}
            style={{
              padding: "0.45rem 0.85rem",
              fontSize: "0.82rem",
              background: "var(--bg-soft)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              cursor: "pointer",
              color: "var(--text)",
            }}
          >
            Select All Pending ({payable.length})
          </button>
        )}
        {payResult && (
          <span
            style={{
              fontSize: "0.85rem",
              color: payResult.startsWith("Error") ? "var(--danger)" : "var(--accent-2)",
            }}
          >
            {payResult}
          </span>
        )}
      </div>
    </div>
  );
}

/* ---- History Tab ---- */

function HistoryTab({ attorney }: { attorney: AttorneyInfo }) {
  const [history, setHistory] = useState<PayoutHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // attorney is accessed if we ever need to scope future queries, suppress the unused warning
  void attorney;

  useEffect(() => {
    apiFetch<PayoutHistoryItem[]>("/gateway/payouts/history")
      .then(setHistory)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="muted">Loading history...</p>;
  if (error) return <p className="error">{error}</p>;

  const totalPaidCents = history
    .filter((h) => h.status === "completed")
    .reduce((s, h) => s + h.amount_cents, 0);

  return (
    <div className="panel stack">
      <div style={{ display: "flex", gap: "1rem", alignItems: "baseline", flexWrap: "wrap" }}>
        <strong>{history.length} transfer{history.length !== 1 ? "s" : ""}</strong>
        {totalPaidCents > 0 && (
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            ${(totalPaidCents / 100).toFixed(2)} successfully disbursed
          </span>
        )}
      </div>

      {history.length === 0 ? (
        <p className="muted">No payout history yet.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--border)", textAlign: "left" }}>
                <th style={{ padding: "0.5rem 0.4rem" }}>Settlement</th>
                <th style={{ padding: "0.5rem 0.4rem" }}>Recipient</th>
                <th style={{ padding: "0.5rem 0.4rem" }}>Amount</th>
                <th style={{ padding: "0.5rem 0.4rem" }}>Status</th>
                <th style={{ padding: "0.5rem 0.4rem" }}>Transfer ID</th>
                <th style={{ padding: "0.5rem 0.4rem", whiteSpace: "nowrap" }}>Completed</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={item.transfer_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "0.45rem 0.4rem", maxWidth: 180 }}>
                    <span
                      style={{
                        display: "block",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={item.settlement_title}
                    >
                      {item.settlement_title}
                    </span>
                  </td>
                  <td style={{ padding: "0.45rem 0.4rem" }}>
                    <div>{item.email}</div>
                    {(item.first_name || item.last_name) && (
                      <div className="muted" style={{ fontSize: "0.78rem" }}>
                        {[item.first_name, item.last_name].filter(Boolean).join(" ")}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: "0.45rem 0.4rem", whiteSpace: "nowrap" }}>
                    ${(item.amount_cents / 100).toFixed(2)}
                  </td>
                  <td style={{ padding: "0.45rem 0.4rem" }}>
                    <StatusBadge status={item.status} />
                    {item.failure_reason && (
                      <div className="muted" style={{ fontSize: "0.72rem", marginTop: 2 }}>
                        {item.failure_reason}
                      </div>
                    )}
                  </td>
                  <td
                    className="muted"
                    style={{ padding: "0.45rem 0.4rem", fontFamily: "monospace", fontSize: "0.72rem" }}
                  >
                    {item.provider_transfer_id
                      ? item.provider_transfer_id.slice(0, 16) + "…"
                      : "—"}
                  </td>
                  <td
                    className="muted"
                    style={{ padding: "0.45rem 0.4rem", fontSize: "0.78rem", whiteSpace: "nowrap" }}
                  >
                    {item.completed_at ? new Date(item.completed_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ---- Questions Tab ---- */

type SettlementQuestionsState = {
  questions: SettlementQuestion[];
  loading: boolean;
  expanded: boolean;
};

const QUESTION_TYPES = ["text", "yes_no", "date", "amount", "select"] as const;

function QuestionsTab() {
  const [settlements, setSettlements] = useState<Array<{ id: string; title: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [settlementState, setSettlementState] = useState<Record<string, SettlementQuestionsState>>({});
  const [addForms, setAddForms] = useState<
    Record<string, { text: string; type: SettlementQuestion["question_type"]; required: boolean }>
  >({});

  useEffect(() => {
    apiFetch<Array<{ id: string; title: string }>>("/gateway/settlements")
      .then(setSettlements)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const uniqueSettlements = settlements;

  const fetchQuestions = async (settlementId: string) => {
    setSettlementState((prev) => ({
      ...prev,
      [settlementId]: { ...prev[settlementId], loading: true, expanded: true, questions: prev[settlementId]?.questions ?? [] },
    }));
    try {
      const questions = await apiFetch<SettlementQuestion[]>(`/gateway/settlements/${settlementId}/questions`);
      setSettlementState((prev) => ({
        ...prev,
        [settlementId]: { questions, loading: false, expanded: true },
      }));
    } catch {
      setSettlementState((prev) => ({
        ...prev,
        [settlementId]: { ...prev[settlementId], loading: false },
      }));
    }
  };

  const toggleExpand = (settlementId: string) => {
    const current = settlementState[settlementId];
    if (current?.expanded) {
      setSettlementState((prev) => ({
        ...prev,
        [settlementId]: { ...prev[settlementId], expanded: false },
      }));
    } else {
      fetchQuestions(settlementId);
    }
  };

  const seedDefaults = async (settlementId: string) => {
    await apiFetch(`/gateway/settlements/${settlementId}/questions/seed`, { method: "POST" });
    await fetchQuestions(settlementId);
  };

  const addQuestion = async (settlementId: string) => {
    const form = addForms[settlementId];
    if (!form?.text.trim()) return;
    await apiFetch(`/gateway/settlements/${settlementId}/questions`, {
      method: "POST",
      body: JSON.stringify({
        question_text: form.text.trim(),
        question_type: form.type,
        required: form.required,
      }),
    });
    setAddForms((prev) => ({ ...prev, [settlementId]: { text: "", type: "text", required: false } }));
    await fetchQuestions(settlementId);
  };

  const deleteQuestion = async (settlementId: string, questionId: string) => {
    await apiFetch(`/gateway/settlements/${settlementId}/questions/${questionId}`, { method: "DELETE" });
    await fetchQuestions(settlementId);
  };

  if (loading) return <p className="muted">Loading settlements...</p>;
  if (error) return <p className="error">{error}</p>;

  if (uniqueSettlements.length === 0) {
    return (
      <div className="panel">
        <p className="muted">No managed settlements yet.</p>
      </div>
    );
  }

  return (
    <div className="panel stack">
      <strong style={{ fontSize: "1rem" }}>
        {uniqueSettlements.length} settlement{uniqueSettlements.length !== 1 ? "s" : ""}
      </strong>
      {uniqueSettlements.map((s) => {
        const state = settlementState[s.id];
        const questions = state?.questions ?? [];
        const isExpanded = state?.expanded ?? false;
        const isLoading = state?.loading ?? false;
        const form = addForms[s.id] ?? { text: "", type: "text" as const, required: false };

        return (
          <div
            key={s.id}
            style={{
              border: "1px solid var(--border)",
              borderRadius: 12,
              overflow: "hidden",
              marginBottom: "0.5rem",
            }}
          >
            {/* Header */}
            <div
              onClick={() => toggleExpand(s.id)}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "0.75rem 1rem",
                cursor: "pointer",
                background: "var(--bg-soft)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <span style={{ fontWeight: 700, fontSize: "0.92rem" }}>{s.title}</span>
                <span
                  style={{
                    display: "inline-block",
                    padding: "0.15rem 0.5rem",
                    borderRadius: "999px",
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    background: "rgba(104,225,253,0.15)",
                    color: "var(--accent)",
                    border: "1px solid rgba(104,225,253,0.4)",
                  }}
                >
                  {questions.length} question{questions.length !== 1 ? "s" : ""}
                </span>
              </div>
              <span style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                {isExpanded ? "\u25B2" : "\u25BC"}
              </span>
            </div>

            {/* Expanded content */}
            {isExpanded && (
              <div style={{ padding: "0.75rem 1rem" }}>
                {/* Seed button */}
                <div style={{ marginBottom: "0.75rem" }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      seedDefaults(s.id);
                    }}
                    style={{
                      padding: "0.35rem 0.75rem",
                      fontSize: "0.82rem",
                      background: "var(--bg-soft)",
                      border: "1px solid var(--border)",
                      borderRadius: "6px",
                      cursor: "pointer",
                      color: "var(--text)",
                    }}
                  >
                    Seed Defaults
                  </button>
                </div>

                {isLoading && <p className="muted" style={{ fontSize: "0.85rem" }}>Loading questions...</p>}

                {/* Question list */}
                {!isLoading && questions.length === 0 && (
                  <p className="muted" style={{ fontSize: "0.85rem" }}>No questions yet. Seed defaults or add one below.</p>
                )}
                {!isLoading &&
                  questions.map((q) => (
                    <div
                      key={q.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.6rem",
                        padding: "0.45rem 0",
                        borderBottom: "1px solid var(--border)",
                        fontSize: "0.85rem",
                      }}
                    >
                      <span style={{ flex: 1 }}>{q.question_text}</span>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "0.15rem 0.4rem",
                          borderRadius: "999px",
                          fontSize: "0.7rem",
                          fontWeight: 700,
                          background: "rgba(133,255,158,0.12)",
                          color: "var(--accent-2)",
                          border: "1px solid rgba(133,255,158,0.35)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {q.question_type}
                      </span>
                      {q.required && (
                        <span style={{ color: "var(--danger)", fontSize: "0.78rem", fontWeight: 700 }}>
                          required
                        </span>
                      )}
                      <button
                        onClick={() => deleteQuestion(s.id, q.id)}
                        style={{
                          padding: "0.2rem 0.5rem",
                          fontSize: "0.75rem",
                          background: "transparent",
                          border: "1px solid var(--danger)",
                          color: "var(--danger)",
                          borderRadius: "4px",
                          cursor: "pointer",
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  ))}

                {/* Add question form */}
                {!isLoading && (
                  <div
                    style={{
                      display: "flex",
                      gap: "0.5rem",
                      alignItems: "center",
                      flexWrap: "wrap",
                      marginTop: "0.75rem",
                    }}
                  >
                    <input
                      type="text"
                      placeholder="Question text"
                      value={form.text}
                      onChange={(e) =>
                        setAddForms((prev) => ({ ...prev, [s.id]: { ...form, text: e.target.value } }))
                      }
                      style={{ flex: 1, minWidth: 180, fontSize: "0.85rem", padding: "0.45rem 0.65rem", borderRadius: "8px" }}
                    />
                    <select
                      value={form.type}
                      onChange={(e) =>
                        setAddForms((prev) => ({
                          ...prev,
                          [s.id]: { ...form, type: e.target.value as SettlementQuestion["question_type"] },
                        }))
                      }
                      style={{ width: "auto", fontSize: "0.82rem", padding: "0.45rem 0.5rem", borderRadius: "8px" }}
                    >
                      {QUESTION_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                    <label
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.3rem",
                        fontSize: "0.82rem",
                        color: "var(--muted)",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={form.required}
                        onChange={(e) =>
                          setAddForms((prev) => ({ ...prev, [s.id]: { ...form, required: e.target.checked } }))
                        }
                        style={{ width: "auto" }}
                      />
                      Required
                    </label>
                    <button
                      onClick={() => addQuestion(s.id)}
                      disabled={!form.text.trim()}
                      style={{
                        padding: "0.4rem 0.75rem",
                        fontSize: "0.82rem",
                        borderRadius: "6px",
                      }}
                    >
                      Add Question
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
