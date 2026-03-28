"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Loader2, Lightbulb, TrendingDown, Gavel, Trophy, Clock } from "lucide-react";
import { fetchDashboardStats, fetchAppealStats } from "@/lib/api";
import type { DashboardStats, AppealStats } from "@/lib/api";

const FALLBACK_DATA: DashboardStats["denialRatesByPayer"] = [
  {
    payer: "Aetna",
    denialRate: 18,
    cptBreakdown: [
      { cpt: "27447", denialRate: 12 },
      { cpt: "72148", denialRate: 25 },
      { cpt: "29881", denialRate: 15 },
      { cpt: "43239", denialRate: 20 },
    ],
  },
  {
    payer: "UnitedHealth",
    denialRate: 28,
    cptBreakdown: [
      { cpt: "27447", denialRate: 22 },
      { cpt: "72148", denialRate: 38 },
      { cpt: "29881", denialRate: 20 },
      { cpt: "43239", denialRate: 30 },
    ],
  },
  {
    payer: "Cigna",
    denialRate: 22,
    cptBreakdown: [
      { cpt: "27447", denialRate: 18 },
      { cpt: "72148", denialRate: 30 },
      { cpt: "29881", denialRate: 16 },
      { cpt: "43239", denialRate: 24 },
    ],
  },
  {
    payer: "Blue Cross",
    denialRate: 15,
    cptBreakdown: [
      { cpt: "27447", denialRate: 10 },
      { cpt: "72148", denialRate: 20 },
      { cpt: "29881", denialRate: 12 },
      { cpt: "43239", denialRate: 18 },
    ],
  },
  {
    payer: "Humana",
    denialRate: 24,
    cptBreakdown: [
      { cpt: "27447", denialRate: 20 },
      { cpt: "72148", denialRate: 32 },
      { cpt: "29881", denialRate: 18 },
      { cpt: "43239", denialRate: 26 },
    ],
  },
];

const PAYER_TIPS: Record<string, string[]> = {
  Aetna: [
    "Aetna requires documented failure of 6+ weeks conservative treatment for orthopedic procedures.",
    "Include functional outcome measures (KOOS, WOMAC) when available.",
    "Peer-to-peer reviews are typically scheduled within 5 business days of request.",
  ],
  UnitedHealth: [
    "UHC has the highest denial rate - always include comprehensive clinical documentation.",
    "For imaging, document prior diagnostic steps and clinical correlation.",
    "UHC InterQual criteria are strictly applied; reference them explicitly in letters.",
  ],
  Cigna: [
    "Cigna EviCore manages most radiology PAs - submit through their portal for faster processing.",
    "Include medical necessity documentation referencing Cigna's published coverage policies.",
    "Appeals through Cigna must be filed within 180 days of denial.",
  ],
  "Blue Cross": [
    "BCBS has the lowest denial rate - ensure clean submission for fastest turnaround.",
    "BCBS regional variations exist; confirm which plan the patient carries.",
    "Online submission through Availity is preferred and typically processed within 48 hours.",
  ],
  Humana: [
    "Humana requires CMS-compliant documentation for Medicare Advantage members.",
    "Always verify if the patient is on a Humana MA plan vs. commercial plan.",
    "Humana peer reviews can be requested by calling the number on the denial letter.",
  ],
};

const FALLBACK_WINNABLE: AppealStats["most_winnable"] = [
  { code: "CO-16", name: "Claim lacks info", estimated_win_rate: 88, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 10 },
  { code: "CO-4", name: "Invalid procedure code", estimated_win_rate: 85, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 14 },
  { code: "CO-22", name: "Other insurance primary", estimated_win_rate: 75, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 15 },
  { code: "CO-50", name: "Not medically necessary", estimated_win_rate: 71, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 21 },
  { code: "CO-197", name: "No precertification", estimated_win_rate: 62, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 18 },
  { code: "CO-170", name: "Diagnosis not covered", estimated_win_rate: 58, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 20 },
  { code: "CO-151", name: "Payment adjusted", estimated_win_rate: 52, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 22 },
  { code: "CO-119", name: "Benefit max reached", estimated_win_rate: 45, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 30 },
  { code: "CO-96", name: "Non-covered service", estimated_win_rate: 38, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 28 },
  { code: "PR-204", name: "Not covered, member resp", estimated_win_rate: 35, actual_win_rate: null, total_appeals: 0, typical_resolution_days: 25 },
];

export default function IntelligencePage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
  });

  const { data: appealStats } = useQuery({
    queryKey: ["appeal-stats"],
    queryFn: fetchAppealStats,
  });

  const payerData = stats?.denialRatesByPayer ?? FALLBACK_DATA;
  const winnableData = appealStats?.most_winnable ?? FALLBACK_WINNABLE;

  const chartData = payerData.map((p) => ({
    payer: p.payer,
    denialRate: p.denialRate,
  }));

  // Collect all unique CPT codes for the matrix
  const allCPTs = Array.from(
    new Set(payerData.flatMap((p) => p.cptBreakdown.map((c) => c.cpt)))
  ).sort();

  return (
    <div className="space-y-6">
      <div>
        <h1>Payer Intelligence</h1>
        <p className="mt-1 text-sm text-slate-500">
          Denial rate analytics and payer-specific optimization tips
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        </div>
      ) : (
        <>
          {/* Chart */}
          <div className="card">
            <h2 className="mb-4 flex items-center gap-2">
              <TrendingDown size={18} className="text-red-500" />
              Denial Rates by Payer
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="payer" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v: number) => `${v}%`}
                />
                <Tooltip
                  formatter={(value: number) => [`${value}%`, "Denial Rate"]}
                />
                <Bar
                  dataKey="denialRate"
                  fill="#ef4444"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={60}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Payer x CPT Matrix */}
          <div className="card">
            <h2 className="mb-4">Payer x CPT Denial Rate Matrix</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="pb-3 pr-4 text-left text-xs font-medium uppercase text-slate-500">
                      Payer
                    </th>
                    <th className="pb-3 pr-4 text-center text-xs font-medium uppercase text-slate-500">
                      Overall
                    </th>
                    {allCPTs.map((cpt) => (
                      <th
                        key={cpt}
                        className="pb-3 pr-4 text-center text-xs font-medium uppercase text-slate-500"
                      >
                        CPT {cpt}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {payerData.map((payer) => (
                    <tr key={payer.payer} className="hover:bg-slate-50">
                      <td className="py-3 pr-4 font-medium text-slate-800">
                        {payer.payer}
                      </td>
                      <td className="py-3 pr-4 text-center">
                        <DenialCell rate={payer.denialRate} />
                      </td>
                      {allCPTs.map((cpt) => {
                        const breakdown = payer.cptBreakdown.find(
                          (c) => c.cpt === cpt
                        );
                        return (
                          <td key={cpt} className="py-3 pr-4 text-center">
                            {breakdown ? (
                              <DenialCell rate={breakdown.denialRate} />
                            ) : (
                              <span className="text-slate-300">--</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Most Winnable Denials */}
          <div className="card">
            <h2 className="mb-4 flex items-center gap-2">
              <Trophy size={18} className="text-green-500" />
              Most Winnable Denials (by CARC Code)
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="pb-3 pr-4 text-left text-xs font-medium uppercase text-slate-500">
                      CARC Code
                    </th>
                    <th className="pb-3 pr-4 text-left text-xs font-medium uppercase text-slate-500">
                      Description
                    </th>
                    <th className="pb-3 pr-4 text-center text-xs font-medium uppercase text-slate-500">
                      Est. Win Rate
                    </th>
                    <th className="pb-3 pr-4 text-center text-xs font-medium uppercase text-slate-500">
                      Actual Win Rate
                    </th>
                    <th className="pb-3 pr-4 text-center text-xs font-medium uppercase text-slate-500">
                      Avg Days
                    </th>
                    <th className="pb-3 text-center text-xs font-medium uppercase text-slate-500">
                      Appeals Filed
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {winnableData.map((item) => (
                    <tr key={item.code} className="hover:bg-slate-50">
                      <td className="py-3 pr-4 font-mono text-xs font-medium text-slate-800">
                        {item.code}
                      </td>
                      <td className="py-3 pr-4 text-slate-600">
                        {item.name}
                      </td>
                      <td className="py-3 pr-4 text-center">
                        <WinRateCell rate={item.estimated_win_rate} />
                      </td>
                      <td className="py-3 pr-4 text-center">
                        {item.actual_win_rate !== null ? (
                          <WinRateCell rate={item.actual_win_rate} />
                        ) : (
                          <span className="text-slate-300">--</span>
                        )}
                      </td>
                      <td className="py-3 pr-4 text-center text-slate-600">
                        {item.typical_resolution_days}
                      </td>
                      <td className="py-3 text-center text-slate-600">
                        {item.total_appeals}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Appeal Win Rate by Payer */}
          {appealStats?.by_payer && appealStats.by_payer.length > 0 && (
            <div className="card">
              <h2 className="mb-4 flex items-center gap-2">
                <Gavel size={18} className="text-purple-500" />
                Appeal Win Rate by Payer
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      <th className="pb-3 pr-4 text-left text-xs font-medium uppercase text-slate-500">Payer</th>
                      <th className="pb-3 pr-4 text-center text-xs font-medium uppercase text-slate-500">Total Appeals</th>
                      <th className="pb-3 pr-4 text-center text-xs font-medium uppercase text-slate-500">Won</th>
                      <th className="pb-3 pr-4 text-center text-xs font-medium uppercase text-slate-500">Lost</th>
                      <th className="pb-3 pr-4 text-center text-xs font-medium uppercase text-slate-500">Win Rate</th>
                      <th className="pb-3 text-center text-xs font-medium uppercase text-slate-500">Avg Days</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {appealStats.by_payer.map((p) => (
                      <tr key={p.payer_name} className="hover:bg-slate-50">
                        <td className="py-3 pr-4 font-medium text-slate-800">{p.payer_name}</td>
                        <td className="py-3 pr-4 text-center text-slate-600">{p.total_appeals}</td>
                        <td className="py-3 pr-4 text-center text-green-600 font-medium">{p.won}</td>
                        <td className="py-3 pr-4 text-center text-red-600 font-medium">{p.lost}</td>
                        <td className="py-3 pr-4 text-center">
                          {p.win_rate ? <WinRateCell rate={parseFloat(p.win_rate)} /> : <span className="text-slate-300">--</span>}
                        </td>
                        <td className="py-3 text-center text-slate-600">
                          {p.avg_days_to_overturn ? `${p.avg_days_to_overturn}d` : "--"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Urgent Appeals Widget */}
          {appealStats?.urgent_appeals && appealStats.urgent_appeals.length > 0 && (
            <div className="card border-amber-200 bg-amber-50">
              <h2 className="mb-4 flex items-center gap-2 text-amber-800">
                <Clock size={18} className="text-amber-600" />
                Appeals Needing Attention ({appealStats.urgent_appeals.length} deadline{appealStats.urgent_appeals.length !== 1 ? "s" : ""} approaching)
              </h2>
              <div className="space-y-2">
                {appealStats.urgent_appeals.map((a) => (
                  <div key={a.id} className="flex items-center gap-3 rounded-lg border border-amber-200 bg-white p-3">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-slate-800">
                        {a.payer_name} &middot; CPT {a.cpt_code}
                        {a.denial_reason_code && (
                          <span className="ml-1 font-mono text-xs text-slate-500">({a.denial_reason_code})</span>
                        )}
                      </p>
                      <p className="text-xs text-slate-500">Patient: {a.patient_id}</p>
                    </div>
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                      a.days_remaining <= 3 ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
                    }`}>
                      {a.days_remaining} day{a.days_remaining !== 1 ? "s" : ""} left
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Payer Tips */}
          <div className="card">
            <h2 className="mb-4 flex items-center gap-2">
              <Lightbulb size={18} className="text-yellow-500" />
              Payer-Specific Tips
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              {Object.entries(PAYER_TIPS).map(([payer, tips]) => (
                <div
                  key={payer}
                  className="rounded-lg border border-slate-200 p-4"
                >
                  <h3 className="mb-2 font-semibold text-slate-800">
                    {payer}
                  </h3>
                  <ul className="space-y-1.5">
                    {tips.map((tip, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-xs text-slate-600"
                      >
                        <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-primary-400" />
                        {tip}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function DenialCell({ rate }: { rate: number }) {
  const color =
    rate < 20
      ? "bg-green-100 text-green-700"
      : rate < 30
        ? "bg-yellow-100 text-yellow-700"
        : "bg-red-100 text-red-700";

  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}
    >
      {rate}%
    </span>
  );
}

function WinRateCell({ rate }: { rate: number }) {
  const color =
    rate >= 70
      ? "bg-green-100 text-green-700"
      : rate >= 50
        ? "bg-yellow-100 text-yellow-700"
        : "bg-red-100 text-red-700";

  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}
    >
      {Math.round(rate)}%
    </span>
  );
}
