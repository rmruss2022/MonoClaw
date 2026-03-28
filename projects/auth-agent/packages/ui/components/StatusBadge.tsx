interface StatusBadgeProps {
  status: string;
}

const statusConfig: Record<
  string,
  { bg: string; text: string; dot: string; label: string }
> = {
  draft: {
    bg: "bg-slate-100",
    text: "text-slate-700",
    dot: "bg-slate-400",
    label: "Draft",
  },
  reviewed: {
    bg: "bg-indigo-100",
    text: "text-indigo-700",
    dot: "bg-indigo-400",
    label: "Reviewed",
  },
  submitted: {
    bg: "bg-blue-100",
    text: "text-blue-700",
    dot: "bg-blue-400",
    label: "Submitted",
  },
  pending_decision: {
    bg: "bg-amber-100",
    text: "text-amber-700",
    dot: "bg-amber-400 animate-pulse",
    label: "Pending Decision",
  },
  approved: {
    bg: "bg-green-100",
    text: "text-green-700",
    dot: "bg-green-400",
    label: "Approved",
  },
  denied: {
    bg: "bg-red-100",
    text: "text-red-700",
    dot: "bg-red-400",
    label: "Denied",
  },
  appeal_draft: {
    bg: "bg-orange-100",
    text: "text-orange-700",
    dot: "bg-orange-400",
    label: "Appeal Draft",
  },
  appeal_submitted: {
    bg: "bg-purple-100",
    text: "text-purple-700",
    dot: "bg-purple-400",
    label: "Appeal Submitted",
  },
  appeal_decided: {
    bg: "bg-purple-100",
    text: "text-purple-700",
    dot: "bg-purple-400",
    label: "Appeal Decided",
  },
  appealed: {
    bg: "bg-purple-100",
    text: "text-purple-700",
    dot: "bg-purple-400",
    label: "Appealed",
  },
  closed: {
    bg: "bg-slate-100",
    text: "text-slate-600",
    dot: "bg-slate-400",
    label: "Closed",
  },
};

const fallbackConfig = {
  bg: "bg-slate-100",
  text: "text-slate-600",
  dot: "bg-slate-400",
  label: "Unknown",
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] || fallbackConfig;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${config.bg} ${config.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  );
}
