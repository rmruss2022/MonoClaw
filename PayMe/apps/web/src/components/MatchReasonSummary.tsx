type Props = {
  reasons: {
    matched_features?: string[];
    confidence_breakdown?: Record<string, number>;
  };
};

export function MatchReasonSummary({ reasons }: Props) {
  const matched = reasons.matched_features || [];
  return (
    <div className="stack">
      <div className="muted">Matched features: {matched.join(", ") || "none"}</div>
    </div>
  );
}
