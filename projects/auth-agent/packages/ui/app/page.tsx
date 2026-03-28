"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import {
  FileCheck,
  TrendingUp,
  Clock,
  DollarSign,
  Plus,
  Loader2,
  AlertTriangle,
  Hourglass,
  Activity,
} from "lucide-react";
import StatusBadge from "@/components/StatusBadge";
import {
  fetchDashboardStats,
  fetchPAList,
  fetchAppealStats,
  fetchActivityFeed,
} from "@/lib/api";
import type {
  DashboardStats,
  PARequest,
  AppealStats,
  ActivityEvent,
} from "@/lib/api";

// --- Fallback data ---

const FALLBACK_STATS: DashboardStats = {
  totalPAs: 89,
  approvalRate: 76,
  avgDays: 2.3,
  revenueRecovered: 47250,
  byStatus: { approved: 42, denied: 18, pending: 21, appealed: 8 },
  denialRatesByPayer: [],
};

const fallbackPABase = {
  practiceId: "practice-001",
  practiceName: "Tri-State Orthopedic Group",
  clinicalExtract: null,
  justificationDraft: null,
  justificationFinal: null,
  probabilityFactors: null,
  denialReasonCode: null,
  denialReasonText: null,
  submittedAt: null,
  decisionAt: null,
  outcome: null,
  covermymedsPaId: null,
  estimatedDecisionDate: null,
  statusHistory: [],
};

const FALLBACK_PAS: PARequest[] = [
  { ...fallbackPABase, id: "pa-001", patientId: "PT-10234", cptCode: "27447", icdCodes: ["M17.11"], payerName: "Aetna", payerId: "aetna-001", status: "approved", approvalProbability: 92, createdAt: "2026-03-25T10:30:00Z", updatedAt: "2026-03-25T10:30:00Z", outcome: "approved" },
  { ...fallbackPABase, id: "pa-002", patientId: "PT-10567", cptCode: "72148", icdCodes: ["M54.5"], payerName: "UnitedHealth", payerId: "uhc-001", status: "denied", approvalProbability: 34, createdAt: "2026-03-24T14:00:00Z", updatedAt: "2026-03-24T14:00:00Z", outcome: "denied", denialReasonCode: "CO-50" },
  { ...fallbackPABase, id: "pa-003", patientId: "PT-10891", cptCode: "29881", icdCodes: ["M23.611"], payerName: "Cigna", payerId: "cigna-001", status: "submitted", approvalProbability: 68, createdAt: "2026-03-23T09:15:00Z", updatedAt: "2026-03-23T09:15:00Z" },
  { ...fallbackPABase, id: "pa-004", patientId: "PT-11002", cptCode: "43239", icdCodes: ["K21.0"], payerName: "Blue Cross", payerId: "bcbs-001", practiceId: "practice-002", status: "appealed", approvalProbability: 55, createdAt: "2026-03-22T11:45:00Z", updatedAt: "2026-03-22T11:45:00Z", outcome: "denied" },
  { ...fallbackPABase, id: "pa-005", patientId: "PT-11234", cptCode: "64483", icdCodes: ["M54.16"], payerName: "Aetna", payerId: "aetna-001", status: "draft", approvalProbability: 71, createdAt: "2026-03-21T16:00:00Z", updatedAt: "2026-03-21T16:00:00Z" },
];

const FALLBACK_ACTIVITY: ActivityEvent[] = [
  { id: "evt-1", pa_id: "pa-001", patient_id: "PT-10234", payer_name: "Aetna", cpt_code: "27447", event: "approved", detail: "PA approved by Aetna", timestamp: "2026-03-27T08:30:00Z" },
  { id: "evt-2", pa_id: "pa-003", patient_id: "PT-10891", payer_name: "Cigna", cpt_code: "29881", event: "submitted", detail: "PA submitted to Cigna", timestamp: "2026-03-26T16:45:00Z" },
  { id: "evt-3", pa_id: "pa-002", patient_id: "PT-10567", payer_name: "UnitedHealth", cpt_code: "72148", event: "denied", detail: "PA denied by UnitedHealth (CO-50)", timestamp: "2026-03-26T10:15:00Z" },
  { id: "evt-4", pa_id: "pa-004", patient_id: "PT-11002", payer_name: "Blue Cross", cpt_code: "43239", event: "appeal", detail: "Appeal filed with Blue Cross", timestamp: "2026-03-25T14:20:00Z" },
  { id: "evt-5", pa_id: "pa-005", patient_id: "PT-11234", payer_name: "Aetna", cpt_code: "64483", event: "draft", detail: "Draft PA created for Aetna", timestamp: "2026-03-25T09:00:00Z" },
];

const STATUS_COLORS: Record<string, string> = {
  approved: "#22c55e",
  denied: "#ef4444",
  pending: "#eab308",
  appealed: "#a855f7",
};

// --- CPT code priority for sorting ---
const CPT_PRIORITY: Record<string, number> = {
  "27447": 100, // total knee replacement
  "27130": 100, // hip replacement
  "29881": 80,  // knee arthroscopy
  "43239": 70,  // upper GI endoscopy
  "64483": 60,  // epidural injection
  "72148": 50,  // lumbar MRI
  "99213": 10,  // office visit
  "99214": 10,
};

function getCptPriority(cptCode: string): number {
  return CPT_PRIORITY[cptCode] ?? 30;
}

// --- Animated count-up hook ---

function useCountUp(target: number, duration = 1200): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target === 0) return;
    const start = performance.now();
    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setValue(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, [target, duration]);
  return value;
}

// --- Relative time helper ---

function relativeTime(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return then.toLocaleDateString();
}

// --- Event dot color ---

const EVENT_DOT_COLORS: Record<string, string> = {
  approved: "bg-green-500",
  denied: "bg-red-500",
  submitted: "bg-blue-500",
  draft: "bg-gray-400",
  appeal: "bg-purple-500",
};

// --- Animated Stat Card ---

interface AnimatedStatCardProps {
  label: string;
  target: number;
  prefix?: string;
  suffix?: string;
  icon: React.ReactNode;
  color: string;
  formatValue?: (v: number) => string;
}

function AnimatedStatCard({
  label,
  target,
  prefix = "",
  suffix = "",
  icon,
  color,
  formatValue,
}: AnimatedStatCardProps) {
  const animated = useCountUp(target);
  const display = formatValue
    ? formatValue(animated)
    : `${prefix}${animated.toLocaleString()}${suffix}`;

  return (
    <div className="card flex items-center gap-4">
      <div className={`rounded-lg p-3 ${color}`}>{icon}</div>
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="text-2xl font-bold text-slate-900">{display}</p>
      </div>
    </div>
  );
}

// --- Sort pending PAs by urgency ---

function sortPAsByUrgency(
  pas: PARequest[],
  urgentAppeals?: AppealStats["urgent_appeals"]
): PARequest[] {
  const urgentDeadlineMap = new Map<string, number>();
  if (urgentAppeals) {
    for (const a of urgentAppeals) {
      urgentDeadlineMap.set(a.pa_request_id, a.days_remaining);
    }
  }

  return [...pas].sort((a, b) => {
    // Pending PAs come first
    const aPending = a.status === "submitted" || a.status === "draft" || a.status === "appealed";
    const bPending = b.status === "submitted" || b.status === "draft" || b.status === "appealed";
    if (aPending && !bPending) return -1;
    if (!aPending && bPending) return 1;

    // Among pending: appeal deadline approaching first
    const aDeadline = urgentDeadlineMap.get(a.id) ?? Infinity;
    const bDeadline = urgentDeadlineMap.get(b.id) ?? Infinity;
    if (aDeadline !== bDeadline) return aDeadline - bDeadline;

    // Higher value CPT codes first
    const aCpt = getCptPriority(a.cptCode);
    const bCpt = getCptPriority(b.cptCode);
    if (aCpt !== bCpt) return bCpt - aCpt;

    // Then by date (newest first)
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });
}

// --- Main Dashboard ---

export default function DashboardPage() {
  const {
    data: stats,
    isLoading: statsLoading,
  } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
  });

  const {
    data: paList,
    isLoading: paLoading,
  } = useQuery({
    queryKey: ["pa-list"],
    queryFn: fetchPAList,
  });

  const { data: appealStats } = useQuery({
    queryKey: ["appeal-stats"],
    queryFn: fetchAppealStats,
  });

  const [activityFeed, setActivityFeed] = useState<ActivityEvent[]>([]);
  const [activityLoaded, setActivityLoaded] = useState(false);

  useEffect(() => {
    fetchActivityFeed()
      .then((data) => {
        setActivityFeed(data);
        setActivityLoaded(true);
      })
      .catch(() => {
        setActivityFeed(FALLBACK_ACTIVITY);
        setActivityLoaded(true);
      });
  }, []);

  const displayStats = stats ?? FALLBACK_STATS;
  const displayPAs = paList ?? FALLBACK_PAS;
  const sortedPAs = sortPAsByUrgency(displayPAs, appealStats?.urgent_appeals);

  const chartData = Object.entries(displayStats.byStatus).map(
    ([name, value]) => ({ name: name.charAt(0).toUpperCase() + name.slice(1), value })
  );

  const hasChartData = chartData.some((d) => d.value > 0);
  const timeSavedHours = ((displayStats.totalPAs * 24) / 60).toFixed(1);

  // --- Empty state ---
  if (!statsLoading && !paLoading && displayPAs.length === 0) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="card max-w-md text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary-50">
            <FileCheck className="h-8 w-8 text-primary-600" />
          </div>
          <h2 className="mb-2 text-xl font-semibold text-slate-900">
            No prior authorizations yet
          </h2>
          <p className="mb-6 text-sm text-slate-500">
            Get started by creating your first prior authorization request.
          </p>
          <Link
            href="/pa/new"
            className="btn-primary inline-flex items-center gap-2 text-base"
          >
            Start your first PA
            <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1>Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">
            Prior authorization overview and recent activity
          </p>
        </div>
        <Link href="/pa/new" className="btn-primary flex items-center gap-2">
          <Plus size={16} />
          New PA Request
        </Link>
      </div>

      {/* Stats Row - Animated */}
      {statsLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <AnimatedStatCard
            label="Total PAs (this month)"
            target={displayStats.totalPAs}
            icon={<FileCheck size={20} className="text-primary-600" />}
            color="bg-primary-50"
          />
          <AnimatedStatCard
            label="Approval Rate"
            target={displayStats.approvalRate}
            suffix="%"
            icon={<TrendingUp size={20} className="text-green-600" />}
            color="bg-green-50"
          />
          <AnimatedStatCard
            label="Avg Processing Time"
            target={Math.round(displayStats.avgDays * 10)}
            formatValue={(v) => `${(v / 10).toFixed(1)} days`}
            icon={<Clock size={20} className="text-yellow-600" />}
            color="bg-yellow-50"
          />
          <AnimatedStatCard
            label="$ Recovered"
            target={displayStats.revenueRecovered}
            prefix="$"
            icon={<DollarSign size={20} className="text-emerald-600" />}
            color="bg-emerald-50"
          />
        </div>
      )}

      {/* Time Saved Widget */}
      {!statsLoading && (
        <div className="card flex items-center gap-4 border-l-4 border-primary-500">
          <div className="rounded-lg bg-primary-50 p-3">
            <Hourglass size={24} className="text-primary-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">
              Time Saved This Month
            </p>
            <p className="text-2xl font-bold text-slate-900">
              {timeSavedHours} hours saved{" "}
              <span className="text-base font-normal text-slate-500">
                vs manual process
              </span>
            </p>
            <p className="text-xs text-slate-400">
              Based on 24 min per PA &times; {displayStats.totalPAs} PAs
              processed
            </p>
          </div>
        </div>
      )}

      {/* Charts Row + Activity Feed */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Status Chart */}
        <div className="card">
          <h2 className="mb-4">PAs by Status</h2>
          {hasChartData ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={
                        STATUS_COLORS[entry.name.toLowerCase()] ?? "#94a3b8"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center py-12 text-sm text-slate-400">
              No data yet
            </div>
          )}
        </div>

        {/* Probability Distribution Chart */}
        <div className="card">
          <h2 className="mb-4">Probability Distribution</h2>
          <ProbabilityDistribution pas={displayPAs} />
        </div>

        {/* Recent Activity Feed */}
        <div className="card">
          <div className="mb-4 flex items-center gap-2">
            <Activity size={18} className="text-slate-500" />
            <h2>Recent Activity</h2>
          </div>
          {!activityLoaded ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-primary-600" />
            </div>
          ) : activityFeed.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-sm text-slate-400">
              No data yet
            </div>
          ) : (
            <div className="space-y-3 max-h-[260px] overflow-y-auto pr-1">
              {activityFeed.slice(0, 10).map((evt) => (
                <Link
                  key={evt.id}
                  href={`/pa/${evt.pa_id}`}
                  className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-slate-50"
                >
                  <span
                    className={`mt-1.5 h-2.5 w-2.5 flex-shrink-0 rounded-full ${
                      EVENT_DOT_COLORS[evt.event] ?? "bg-gray-400"
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-700 truncate">
                      {evt.detail}
                    </p>
                    <p className="text-xs text-slate-400">
                      {relativeTime(evt.timestamp)}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Urgent Appeals Widget */}
      {appealStats?.urgent_appeals && appealStats.urgent_appeals.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={18} className="text-amber-600" />
            <h2 className="text-sm font-semibold text-amber-800">
              {appealStats.urgent_appeals.length} appeal{appealStats.urgent_appeals.length !== 1 ? "s" : ""} need attention (deadline approaching)
            </h2>
          </div>
          <div className="space-y-2">
            {appealStats.urgent_appeals.slice(0, 3).map((a) => (
              <Link
                key={a.id}
                href={`/pa/${a.pa_request_id}`}
                className="flex items-center gap-3 rounded-lg border border-amber-200 bg-white p-2.5 hover:bg-amber-50 transition-colors"
              >
                <div className="flex-1">
                  <p className="text-xs font-medium text-slate-700">
                    {a.payer_name} &middot; CPT {a.cpt_code}
                    {a.denial_reason_code && <span className="ml-1 font-mono text-slate-400">({a.denial_reason_code})</span>}
                  </p>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  a.days_remaining <= 3 ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
                }`}>
                  {a.days_remaining}d left
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Recent PAs Table */}
      <div className="grid grid-cols-1 gap-6">
        <div className="card">
          <h2 className="mb-4">Recent PA Requests</h2>
          {paLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <th className="pb-3 pr-4 font-medium">Patient ID</th>
                    <th className="pb-3 pr-4 font-medium">CPT Code</th>
                    <th className="pb-3 pr-4 font-medium">Payer</th>
                    <th className="pb-3 pr-4 font-medium">Status</th>
                    <th className="pb-3 pr-4 font-medium">Probability</th>
                    <th className="pb-3 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sortedPAs.map((pa) => (
                    <tr
                      key={pa.id}
                      className="cursor-pointer transition-colors hover:bg-slate-50"
                    >
                      <td className="py-3 pr-4">
                        <Link
                          href={`/pa/${pa.id}`}
                          className="font-medium text-primary-600 hover:text-primary-800"
                        >
                          {pa.patientId}
                        </Link>
                      </td>
                      <td className="py-3 pr-4 font-mono text-xs">
                        {pa.cptCode}
                      </td>
                      <td className="py-3 pr-4">{pa.payerName}</td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={pa.status} />
                      </td>
                      <td className="py-3 pr-4">
                        <span
                          className={`font-semibold ${
                            pa.approvalProbability < 40
                              ? "text-red-600"
                              : pa.approvalProbability <= 70
                                ? "text-yellow-600"
                                : "text-green-600"
                          }`}
                        >
                          {pa.approvalProbability}%
                        </span>
                      </td>
                      <td className="py-3 text-slate-500">
                        {new Date(pa.createdAt).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Probability Distribution Chart ---

const BUCKET_COLORS: Record<string, string> = {
  "0-30%": "#ef4444",
  "31-50%": "#f97316",
  "51-70%": "#eab308",
  "71-85%": "#84cc16",
  "86-100%": "#22c55e",
};

function ProbabilityDistribution({ pas }: { pas: PARequest[] }) {
  const pendingPAs = pas.filter(
    (pa) => pa.status === "draft" || pa.status === "submitted"
  );

  const buckets = [
    { name: "0-30%", min: 0, max: 30 },
    { name: "31-50%", min: 31, max: 50 },
    { name: "51-70%", min: 51, max: 70 },
    { name: "71-85%", min: 71, max: 85 },
    { name: "86-100%", min: 86, max: 100 },
  ];

  const data = buckets.map((bucket) => ({
    name: bucket.name,
    count: pendingPAs.filter(
      (pa) =>
        pa.approvalProbability >= bucket.min &&
        pa.approvalProbability <= bucket.max
    ).length,
  }));

  if (pendingPAs.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-slate-400">
        No data yet
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
        <Tooltip
          formatter={(value: number) => [`${value} PAs`, "Count"]}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell
              key={entry.name}
              fill={BUCKET_COLORS[entry.name] ?? "#94a3b8"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
