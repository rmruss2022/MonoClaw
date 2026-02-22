type Props = {
  reasons: {
    matched_features?: string[];
    confidence_breakdown?: Record<string, number>;
  };
};

export function MatchReasonSummary({ reasons }: Props) {
  const matched = reasons.matched_features || [];
  const confidence = reasons.confidence_breakdown?.rules ?? 0;
  return (
    <div>
      <div>Matched features: {matched.join(", ") || "none"}</div>
      <div>Rules confidence: {confidence.toFixed(2)}</div>
    </div>
  );
}
