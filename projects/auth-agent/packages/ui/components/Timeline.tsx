"use client";

import {
  CheckCircle2,
  XCircle,
  Clock,
  Send,
  FileText,
  Gavel,
  ArrowRight,
  AlertTriangle,
} from "lucide-react";

export interface TimelineEvent {
  from: string | null;
  to: string;
  actor: string;
  detail: string;
  timestamp: string;
}

interface TimelineProps {
  events: TimelineEvent[];
  currentStatus: string;
  submittedAt?: string | null;
}

const statusIcons: Record<string, React.ReactNode> = {
  draft: <FileText size={14} />,
  reviewed: <CheckCircle2 size={14} />,
  submitted: <Send size={14} />,
  pending_decision: <Clock size={14} />,
  approved: <CheckCircle2 size={14} />,
  denied: <XCircle size={14} />,
  appeal_draft: <Gavel size={14} />,
  appeal_submitted: <Send size={14} />,
  appeal_decided: <AlertTriangle size={14} />,
  closed: <CheckCircle2 size={14} />,
};

const statusColors: Record<string, string> = {
  draft: "bg-slate-400",
  reviewed: "bg-indigo-500",
  submitted: "bg-blue-500",
  pending_decision: "bg-amber-500",
  approved: "bg-green-500",
  denied: "bg-red-500",
  appeal_draft: "bg-orange-500",
  appeal_submitted: "bg-purple-500",
  appeal_decided: "bg-purple-500",
  closed: "bg-slate-500",
};

function formatTimestamp(ts: string) {
  const d = new Date(ts);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatActor(actor: string) {
  if (actor === "system") return "System";
  if (actor === "staff") return "Staff";
  return actor;
}

export default function Timeline({
  events,
  currentStatus,
  submittedAt,
}: TimelineProps) {
  // Calculate days pending for active PAs
  let daysPending: number | null = null;
  if (
    submittedAt &&
    ["submitted", "pending_decision"].includes(currentStatus)
  ) {
    daysPending = Math.floor(
      (Date.now() - new Date(submittedAt).getTime()) / 86400000
    );
  }

  if (!events || events.length === 0) {
    return (
      <p className="text-sm text-slate-500">No timeline events yet.</p>
    );
  }

  return (
    <div className="space-y-1">
      {/* Days pending counter */}
      {daysPending !== null && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
          <Clock size={16} className="text-amber-600" />
          <span className="text-sm font-medium text-amber-800">
            {daysPending === 0
              ? "Submitted today"
              : `${daysPending} day${daysPending !== 1 ? "s" : ""} pending`}
          </span>
        </div>
      )}

      {/* Timeline */}
      <div className="relative space-y-0">
        {events.map((event, i) => {
          const isLast = i === events.length - 1;
          const isCurrent = isLast;
          const color = statusColors[event.to] || "bg-slate-400";
          const icon = statusIcons[event.to] || <ArrowRight size={14} />;

          return (
            <div key={i} className="flex gap-4 pb-6 last:pb-0">
              {/* Dot + line */}
              <div className="relative flex flex-col items-center">
                <div
                  className={`z-10 flex h-7 w-7 items-center justify-center rounded-full text-white ${color} ${
                    isCurrent ? "ring-2 ring-offset-2 ring-primary-400" : ""
                  }`}
                >
                  {icon}
                </div>
                {!isLast && (
                  <div className="absolute left-1/2 top-7 h-full w-0.5 -translate-x-1/2 bg-slate-200" />
                )}
              </div>

              {/* Content */}
              <div className="-mt-0.5 flex-1">
                <div className="flex items-center gap-2">
                  <p
                    className={`text-sm font-medium ${
                      isCurrent ? "text-slate-900" : "text-slate-700"
                    }`}
                  >
                    {event.to
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (c) => c.toUpperCase())}
                  </p>
                  <span className="text-xs text-slate-400">
                    {formatActor(event.actor)}
                  </span>
                </div>
                {event.detail && (
                  <p className="text-xs text-slate-500">{event.detail}</p>
                )}
                <p className="mt-0.5 text-xs text-slate-400">
                  {formatTimestamp(event.timestamp)}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
