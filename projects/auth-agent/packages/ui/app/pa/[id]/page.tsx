"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useCallback } from "react";
import {
  ArrowLeft,
  Clock,
  FileText,
  ScrollText,
  Loader2,
  AlertTriangle,
  Gavel,
  Send,
  RefreshCw,
  CheckCircle2,
  FileDown,
  ChevronDown,
  ChevronRight,
  Code,
  Pill,
  DollarSign,
  Stethoscope,
} from "lucide-react";
import StatusBadge from "@/components/StatusBadge";
import ProbabilityGauge from "@/components/ProbabilityGauge";
import Timeline from "@/components/Timeline";
import {
  fetchPA,
  submitPA,
  refreshPA,
  generateAppeal,
  submitAppeal,
  fetchAppeals,
  type PARequest,
  type StatusHistoryEvent,
  type CarcStrategy,
} from "@/lib/api";

type TabKey = "extract" | "letter" | "timeline" | "appeal";

const FALLBACK_PA: PARequest = {
  id: "pa-001",
  patientId: "PT-10234",
  cptCode: "27447",
  icdCodes: ["M17.11"],
  payerName: "Aetna",
  payerId: "aetna-001",
  practiceId: "practice-001",
  practiceName: "Tri-State Orthopedic Group",
  status: "approved",
  approvalProbability: 92,
  clinicalExtract: {
    diagnosis: "Primary osteoarthritis, right knee",
    severity: "Severe, bone-on-bone",
    conservativeTreatment: [
      "Physical therapy x 12 weeks",
      "NSAIDs",
      "Corticosteroid injection x 3",
    ],
    functionalLimitation:
      "Unable to walk more than 1 block, difficulty with stairs",
    bmi: 28.4,
  },
  justificationDraft:
    "To: Aetna Medical Review Department\nFrom: Attending Physician\nRe: Prior Authorization - CPT 27447\n\nDear Medical Director,\n\nI am writing to request authorization for total knee arthroplasty (CPT 27447) for patient PT-10234.\n\nThe patient presents with severe primary osteoarthritis of the right knee (ICD-10: M17.11) with bone-on-bone changes confirmed on imaging. Conservative management over 18 months including physical therapy, NSAIDs, and corticosteroid injections has failed to provide adequate relief.\n\nThe patient experiences significant functional limitation, unable to walk more than one block or navigate stairs independently.\n\nThis procedure is medically necessary and consistent with Aetna's clinical policy guidelines for total knee replacement.\n\nSincerely,\nAttending Physician",
  justificationFinal: null,
  probabilityFactors: [
    {
      factor: "Strong clinical documentation",
      impact: "positive",
      detail: "Strong clinical documentation supports approval",
    },
    {
      factor: "Conservative treatment documented",
      impact: "positive",
      detail: "Conservative treatment well-documented",
    },
  ],
  denialReasonCode: null,
  denialReasonText: null,
  submittedAt: "2026-03-25T10:40:00Z",
  decisionAt: "2026-03-26T14:00:00Z",
  outcome: "approved",
  createdAt: "2026-03-25T10:30:00Z",
  updatedAt: "2026-03-26T14:00:00Z",
  covermymedsPaId: null,
  estimatedDecisionDate: null,
  statusHistory: [],
};

// CPT code to estimated procedure value lookup
const CPT_VALUE_MAP: Record<string, number> = {
  "72148": 1200, "27447": 32000, "70553": 2800, "63650": 45000,
  "J0274": 900, "64483": 1500, "90837": 250, "95910": 800,
  "78452": 3200, "95800": 2500, "43239": 3500, "27130": 35000,
  "72141": 1100, "29881": 8000, "97110": 150, "64490": 1200,
  "22612": 48000, "63030": 28000, "77067": 350, "93306": 1800,
  "93971": 600,
};

function computeEditPercentage(draft: string, final: string): number {
  const draftWords = draft.split(/\s+/);
  const finalWords = final.split(/\s+/);
  const maxLen = Math.max(draftWords.length, finalWords.length);
  if (maxLen === 0) return 0;
  let diffCount = 0;
  for (let i = 0; i < maxLen; i++) {
    if (draftWords[i] !== finalWords[i]) diffCount++;
  }
  return Math.round((diffCount / maxLen) * 100);
}

function paragraphsMatch(a: string, b: string): boolean {
  return a.trim() === b.trim();
}

function buildFallbackTimeline(pa: PARequest): StatusHistoryEvent[] {
  const events: StatusHistoryEvent[] = [];
  events.push({
    from: null,
    to: "draft",
    actor: "system",
    detail: "PA request created",
    timestamp: pa.createdAt,
  });
  if (pa.clinicalExtract) {
    events.push({
      from: "draft",
      to: "draft",
      actor: "system",
      detail: "AI extracted clinical facts from notes",
      timestamp: pa.createdAt,
    });
  }
  if (pa.justificationDraft) {
    events.push({
      from: "draft",
      to: "reviewed",
      actor: "staff",
      detail: `Justification letter generated — ${pa.approvalProbability}% probability`,
      timestamp: pa.createdAt,
    });
  }
  if (pa.submittedAt) {
    events.push({
      from: "reviewed",
      to: "submitted",
      actor: "staff",
      detail: `PA submitted to ${pa.payerName}`,
      timestamp: pa.submittedAt,
    });
  }
  if (pa.decisionAt && pa.outcome) {
    events.push({
      from: "pending_decision",
      to: pa.outcome,
      actor: "system",
      detail: `PA ${pa.outcome} by ${pa.payerName}${pa.denialReasonCode ? ` (${pa.denialReasonCode})` : ""}`,
      timestamp: pa.decisionAt,
    });
  }
  return events;
}

export default function PADetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id as string;
  const [activeTab, setActiveTab] = useState<TabKey>("timeline");
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [showAppealSubmitModal, setShowAppealSubmitModal] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);
  const [expandedExtractSections, setExpandedExtractSections] = useState<Record<string, boolean>>({
    diagnosis: true,
    treatments: true,
    medications: true,
    other: true,
  });

  const {
    data: pa,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["pa", id],
    queryFn: () => fetchPA(id),
    refetchInterval:
      // Auto-refresh every 15s when pending decision
      (query) => {
        const status = query.state.data?.status;
        return status === "pending_decision" || status === "submitted"
          ? 15000
          : false;
      },
  });

  const submitMutation = useMutation({
    mutationFn: () => submitPA(id),
    onSuccess: () => {
      setShowSubmitModal(false);
      queryClient.invalidateQueries({ queryKey: ["pa", id] });
      queryClient.invalidateQueries({ queryKey: ["pa-list"] });
    },
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshPA(id),
    onSuccess: (data) => {
      if (data.changed) {
        queryClient.invalidateQueries({ queryKey: ["pa", id] });
        queryClient.invalidateQueries({ queryKey: ["pa-list"] });
      }
      refetch();
    },
  });

  const appealMutation = useMutation({
    mutationFn: () => generateAppeal(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pa", id] });
      queryClient.invalidateQueries({ queryKey: ["appeals", id] });
      setActiveTab("appeal");
    },
  });

  const submitAppealMutation = useMutation({
    mutationFn: () => submitAppeal(id),
    onSuccess: () => {
      setShowAppealSubmitModal(false);
      queryClient.invalidateQueries({ queryKey: ["pa", id] });
      queryClient.invalidateQueries({ queryKey: ["appeals", id] });
      queryClient.invalidateQueries({ queryKey: ["pa-list"] });
    },
  });

  const {
    data: appeals,
  } = useQuery({
    queryKey: ["appeals", id],
    queryFn: () => fetchAppeals(id),
    enabled: !!pa && ["denied", "appeal_draft", "appeal_submitted", "appeal_decided"].includes(pa?.status ?? ""),
  });

  const handleSubmit = useCallback(() => {
    submitMutation.mutate();
  }, [submitMutation]);

  const handleRefresh = useCallback(() => {
    refreshMutation.mutate();
  }, [refreshMutation]);

  const handleGenerateAppeal = useCallback(() => {
    appealMutation.mutate();
  }, [appealMutation]);

  const handleSubmitAppeal = useCallback(() => {
    submitAppealMutation.mutate();
  }, [submitAppealMutation]);

  const displayPA = pa ?? FALLBACK_PA;
  const letter = displayPA.justificationFinal || displayPA.justificationDraft;

  // Use status_history from DB, fallback to computed timeline
  const timelineEvents =
    displayPA.statusHistory && displayPA.statusHistory.length > 0
      ? displayPA.statusHistory
      : buildFallbackTimeline(displayPA);

  const rawFactors = (displayPA.probabilityFactors || []) as Record<
    string,
    unknown
  >[];
  const factors = rawFactors.map((f) => ({
    name: (f.name as string) || (f.factor as string) || "",
    impact: typeof f.impact === "number" ? f.impact : 0,
    description: (f.description as string) || (f.detail as string) || "",
    met:
      typeof f.met === "boolean"
        ? f.met
        : (f.impact as string) === "positive",
  }));

  // Can submit: status is reviewed or draft (with a justification)
  const canSubmit =
    ["reviewed", "draft"].includes(displayPA.status) &&
    (displayPA.justificationFinal || displayPA.justificationDraft);

  // Can refresh: submitted or pending
  const canRefresh = ["submitted", "pending_decision"].includes(
    displayPA.status
  );

  // Days pending
  const daysPending =
    displayPA.submittedAt &&
    ["submitted", "pending_decision"].includes(displayPA.status)
      ? Math.floor(
          (Date.now() - new Date(displayPA.submittedAt).getTime()) / 86400000
        )
      : null;

  // Financial impact
  const procedureValue = CPT_VALUE_MAP[displayPA.cptCode] ?? null;
  const dailyDelayCost = procedureValue ? Math.round(procedureValue / 30) : null;

  const showAppealTab = ["denied", "appeal_draft", "appeal_submitted", "appeal_decided"].includes(displayPA.status);

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    {
      key: "timeline",
      label: "Timeline",
      icon: <Clock size={14} />,
    },
    {
      key: "extract",
      label: "Clinical Extract",
      icon: <FileText size={14} />,
    },
    {
      key: "letter",
      label: "Justification Letter",
      icon: <ScrollText size={14} />,
    },
    ...(showAppealTab
      ? [
          {
            key: "appeal" as TabKey,
            label: "Appeal",
            icon: <Gavel size={14} />,
          },
        ]
      : []),
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft size={16} />
        Back
      </button>

      {/* Header */}
      <div className="card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1>PA: {displayPA.patientId}</h1>
              <StatusBadge status={displayPA.status} />
              <a
                href={`/api/pa/${id}/export-pdf`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50 transition-colors"
              >
                <FileDown size={13} />
                Export PDF
              </a>
              {appeals && appeals.length > 0 && (
                <a
                  href={`/api/pa/${id}/export-pdf?type=appeal`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-md border border-purple-200 bg-purple-50 px-2.5 py-1 text-xs font-medium text-purple-600 shadow-sm hover:bg-purple-100 transition-colors"
                >
                  <FileDown size={13} />
                  Export Appeal PDF
                </a>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-500">
              CPT {displayPA.cptCode} &middot; {displayPA.payerName}
            </p>
            <p className="mt-0.5 text-xs text-slate-400">
              Created {new Date(displayPA.createdAt).toLocaleString()}
            </p>

            {/* CoverMyMeds reference */}
            {displayPA.covermymedsPaId && (
              <p className="mt-1 text-xs text-slate-500">
                <span className="font-medium">CMM Ref:</span>{" "}
                <span className="font-mono">
                  {displayPA.covermymedsPaId}
                </span>
              </p>
            )}

            {/* Estimated decision date */}
            {displayPA.estimatedDecisionDate &&
              ["submitted", "pending_decision"].includes(
                displayPA.status
              ) && (
                <p className="mt-0.5 text-xs text-slate-500">
                  <span className="font-medium">Expected decision:</span>{" "}
                  {new Date(
                    displayPA.estimatedDecisionDate
                  ).toLocaleString()}
                </p>
              )}
          </div>
          <ProbabilityGauge
            probability={displayPA.approvalProbability}
            factors={factors}
            size="lg"
            expandable
          />
        </div>

        {/* Financial Impact Cards */}
        {procedureValue && (
          <div className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 sm:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
                <DollarSign size={12} />
                Estimated Procedure Value
              </div>
              <p className="mt-0.5 text-lg font-semibold text-slate-800">
                ${procedureValue.toLocaleString()}
              </p>
              <p className="text-xs text-slate-400">CPT {displayPA.cptCode}</p>
            </div>
            {dailyDelayCost && daysPending !== null && daysPending > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                <div className="flex items-center gap-1.5 text-xs font-medium text-amber-600">
                  <Clock size={12} />
                  Delayed Care Cost
                </div>
                <p className="mt-0.5 text-lg font-semibold text-amber-800">
                  Est. ${dailyDelayCost.toLocaleString()}/day
                </p>
                <p className="text-xs text-amber-500">
                  ~${(dailyDelayCost * daysPending).toLocaleString()} total ({daysPending} day{daysPending !== 1 ? "s" : ""})
                </p>
              </div>
            )}
            {dailyDelayCost && (daysPending === null || daysPending === 0) && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
                  <Clock size={12} />
                  Daily Delay Cost
                </div>
                <p className="mt-0.5 text-lg font-semibold text-slate-800">
                  Est. ${dailyDelayCost.toLocaleString()}/day
                </p>
                <p className="text-xs text-slate-400">If pending</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Submit Button (only when reviewed/draft with justification) */}
      {canSubmit && (
        <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <Send className="h-5 w-5 text-blue-600" />
          <div className="flex-1">
            <p className="text-sm font-medium text-blue-800">
              Ready for submission to {displayPA.payerName}
            </p>
            <p className="text-xs text-blue-600">
              Review the justification letter, then submit when ready.
            </p>
          </div>
          <button
            onClick={() => setShowSubmitModal(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Send size={16} />
            Submit to Payer
          </button>
        </div>
      )}

      {/* Pending Decision: Refresh + Days Counter */}
      {canRefresh && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
          <Clock className="h-5 w-5 text-amber-600" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-800">
              Awaiting payer decision
              {daysPending !== null && (
                <span className="ml-2 rounded bg-amber-200 px-1.5 py-0.5 text-xs">
                  {daysPending === 0
                    ? "Today"
                    : `${daysPending} day${daysPending !== 1 ? "s" : ""}`}
                </span>
              )}
            </p>
            {displayPA.covermymedsPaId && (
              <p className="text-xs text-amber-600">
                CoverMyMeds ref: {displayPA.covermymedsPaId}
              </p>
            )}
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshMutation.isPending}
            className="btn-primary flex items-center gap-2 bg-amber-600 hover:bg-amber-700"
          >
            <RefreshCw
              size={16}
              className={refreshMutation.isPending ? "animate-spin" : ""}
            />
            {refreshMutation.isPending ? "Checking..." : "Check Status"}
          </button>
        </div>
      )}

      {/* Approved banner */}
      {displayPA.status === "approved" && (
        <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 p-4">
          <CheckCircle2 className="h-5 w-5 text-green-500" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-800">
              Approved by {displayPA.payerName}
            </p>
            {displayPA.decisionAt && (
              <p className="text-xs text-green-600">
                Decision received:{" "}
                {new Date(displayPA.decisionAt).toLocaleString()}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Denied: Appeal Button */}
      {displayPA.status === "denied" && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800">
                This PA was denied by {displayPA.payerName}.
                {displayPA.denialReasonCode && (
                  <span className="ml-1 font-mono text-xs">
                    ({displayPA.denialReasonCode})
                  </span>
                )}
              </p>
              {displayPA.denialReasonText && (
                <p className="text-xs text-red-600">
                  {displayPA.denialReasonText}
                </p>
              )}
            </div>
            <button
              onClick={handleGenerateAppeal}
              disabled={appealMutation.isPending}
              className="btn-primary flex items-center gap-2 bg-red-600 hover:bg-red-700"
            >
              {appealMutation.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Gavel size={16} />
                  Generate Appeal
                </>
              )}
            </button>
          </div>
          <CarcStrategyTip denialCode={displayPA.denialReasonCode} />
        </div>
      )}

      {/* Appeal Draft: Review + Submit */}
      {displayPA.status === "appeal_draft" && appeals && appeals.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg border border-purple-200 bg-purple-50 p-4">
            <Gavel className="h-5 w-5 text-purple-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-purple-800">
                Appeal draft ready for review
              </p>
              {appeals?.[0]?.deadline_date && (
                <p className="text-xs text-purple-600">
                  <DeadlineBadge deadline={appeals?.[0]?.deadline_date} />
                </p>
              )}
              {appeals?.[0]?.carc_strategy && (
                <p className="mt-1 text-xs text-purple-600">
                  {(appeals?.[0]?.carc_strategy as CarcStrategy).success_rate_estimate}% historical overturn rate for {(appeals?.[0]?.carc_strategy as CarcStrategy).code} denials
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleGenerateAppeal}
                disabled={appealMutation.isPending}
                className="rounded-lg border border-purple-300 px-3 py-2 text-sm text-purple-700 hover:bg-purple-100"
              >
                {appealMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  "Regenerate"
                )}
              </button>
              <button
                onClick={() => setShowAppealSubmitModal(true)}
                className="btn-primary flex items-center gap-2 bg-purple-600 hover:bg-purple-700"
              >
                <Send size={16} />
                Submit Appeal
              </button>
            </div>
          </div>
          <CarcStrategyTip denialCode={displayPA.denialReasonCode} />
        </div>
      )}

      {/* Appeal Submitted: Waiting */}
      {displayPA.status === "appeal_submitted" && (
        <div className="flex items-center gap-3 rounded-lg border border-purple-200 bg-purple-50 p-4">
          <Clock className="h-5 w-5 text-purple-600" />
          <div className="flex-1">
            <p className="text-sm font-medium text-purple-800">
              Appeal submitted — awaiting decision
            </p>
            {appeals && appeals[0]?.deadline_date && (
              <p className="text-xs text-purple-600">
                <DeadlineBadge deadline={appeals?.[0]?.deadline_date} />
              </p>
            )}
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshMutation.isPending}
            className="btn-primary flex items-center gap-2 bg-purple-600 hover:bg-purple-700"
          >
            <RefreshCw
              size={16}
              className={refreshMutation.isPending ? "animate-spin" : ""}
            />
            {refreshMutation.isPending ? "Checking..." : "Check Status"}
          </button>
        </div>
      )}

      {/* Tabs */}
      <div>
        <div className="flex border-b border-slate-200">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "border-primary-600 text-primary-700"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        <div className="card mt-4 rounded-t-none border-t-0">
          {/* Timeline */}
          {activeTab === "timeline" && (
            <Timeline
              events={timelineEvents}
              currentStatus={displayPA.status}
              submittedAt={displayPA.submittedAt}
            />
          )}

          {/* Clinical Extract */}
          {activeTab === "extract" && (
            <div>
              {displayPA.clinicalExtract ? (
                <ClinicalExtractView
                  extract={displayPA.clinicalExtract}
                  showRawJson={showRawJson}
                  onToggleRawJson={() => setShowRawJson(!showRawJson)}
                  expandedSections={expandedExtractSections}
                  onToggleSection={(key) =>
                    setExpandedExtractSections((prev) => ({
                      ...prev,
                      [key]: !prev[key],
                    }))
                  }
                />
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="rounded-full bg-slate-100 p-3">
                    <Stethoscope className="h-8 w-8 text-slate-300" />
                  </div>
                  <p className="mt-3 text-sm font-medium text-slate-600">
                    No clinical extract available
                  </p>
                  <p className="mt-1 max-w-xs text-xs text-slate-400">
                    Upload clinical notes and run analysis to extract structured data.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Justification Letter */}
          {activeTab === "letter" && (
            <div>
              {displayPA.justificationDraft && displayPA.justificationFinal ? (
                <LetterDiffView
                  draft={displayPA.justificationDraft}
                  final={displayPA.justificationFinal}
                />
              ) : letter ? (
                <div className="whitespace-pre-wrap rounded-lg bg-slate-50 p-4 font-mono text-sm text-slate-700">
                  {letter}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="rounded-full bg-slate-100 p-3">
                    <ScrollText className="h-8 w-8 text-slate-300" />
                  </div>
                  <p className="mt-3 text-sm font-medium text-slate-600">
                    No justification letter generated yet
                  </p>
                  <p className="mt-1 max-w-xs text-xs text-slate-400">
                    Run the AI analysis to generate a letter.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Appeal Letter */}
          {activeTab === "appeal" && (
            <div className="space-y-4">
              {appeals && appeals.length > 0 ? (
                <>
                  {/* Split view: Original PA left, Appeal right */}
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <div>
                      <h3 className="mb-2 text-sm font-semibold text-slate-700">
                        Original Justification
                      </h3>
                      <div className="max-h-[500px] overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-mono text-xs text-slate-600">
                        {letter || "No original justification available"}
                      </div>
                    </div>
                    <div>
                      <h3 className="mb-2 text-sm font-semibold text-purple-700">
                        Appeal Letter
                      </h3>
                      <div className="max-h-[500px] overflow-y-auto whitespace-pre-wrap rounded-lg border border-purple-200 bg-purple-50 p-3 font-mono text-xs text-purple-900">
                        {appeals?.[0]?.appeal_final || appeals?.[0]?.appeal_draft || "No appeal draft available"}
                      </div>
                    </div>
                  </div>

                  {/* Appeal metadata */}
                  {appeals?.[0]?.carc_strategy && (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <h3 className="mb-1 text-xs font-semibold uppercase text-slate-500">
                        CARC Strategy Applied
                      </h3>
                      <p className="text-sm font-medium text-slate-800">
                        {(appeals?.[0]?.carc_strategy as CarcStrategy).code}: {(appeals?.[0]?.carc_strategy as CarcStrategy).name}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {(appeals?.[0]?.carc_strategy as CarcStrategy).strategy}
                      </p>
                    </div>
                  )}

                  {/* All appeals history */}
                  {appeals.length > 1 && (
                    <div>
                      <h3 className="mb-2 text-sm font-semibold text-slate-700">
                        Appeal History
                      </h3>
                      <div className="space-y-2">
                        {appeals.map((appeal, i) => (
                          <div
                            key={appeal.id}
                            className="rounded border border-slate-200 p-2 text-xs"
                          >
                            <span className="font-medium">
                              #{appeals.length - i}: {appeal.escalation_type}
                            </span>
                            {appeal.outcome && (
                              <span
                                className={`ml-2 rounded-full px-2 py-0.5 text-xs font-medium ${
                                  appeal.outcome === "approved"
                                    ? "bg-green-100 text-green-700"
                                    : "bg-red-100 text-red-700"
                                }`}
                              >
                                {appeal.outcome}
                              </span>
                            )}
                            {appeal.deadline_date && !appeal.outcome && (
                              <span className="ml-2">
                                <DeadlineBadge deadline={appeal.deadline_date} />
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-8">
                  <Gavel className="mx-auto h-8 w-8 text-slate-300" />
                  <p className="mt-2 text-sm text-slate-500">
                    No appeal generated yet.
                  </p>
                  {displayPA.status === "denied" && (
                    <button
                      onClick={handleGenerateAppeal}
                      disabled={appealMutation.isPending}
                      className="btn-primary mt-3 inline-flex items-center gap-2"
                    >
                      {appealMutation.isPending ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <Gavel size={16} />
                          Generate Appeal
                        </>
                      )}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Appeal Submit Confirmation Modal */}
      {showAppealSubmitModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-slate-900">
              Submit Appeal to {displayPA.payerName}?
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              This will submit your appeal letter to {displayPA.payerName} for reconsideration of the denied authorization.
            </p>

            {appeals && appeals[0]?.deadline_date && (
              <div className="mt-3 rounded-lg bg-purple-50 p-3">
                <p className="text-xs text-purple-800">
                  <DeadlineBadge deadline={appeals?.[0]?.deadline_date} />
                </p>
              </div>
            )}

            {submitAppealMutation.isError && (
              <div className="mt-3 rounded bg-red-50 p-2 text-xs text-red-700">
                Appeal submission failed. Please try again.
              </div>
            )}

            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => setShowAppealSubmitModal(false)}
                className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
                disabled={submitAppealMutation.isPending}
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitAppeal}
                disabled={submitAppealMutation.isPending}
                className="btn-primary flex items-center gap-2 bg-purple-600 hover:bg-purple-700"
              >
                {submitAppealMutation.isPending ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <Send size={16} />
                    Confirm Appeal Submission
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Submit Confirmation Modal */}
      {showSubmitModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-slate-900">
              Submit to {displayPA.payerName}?
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              This will transmit patient information to{" "}
              {displayPA.payerName} via CoverMyMeds for prior
              authorization review.
            </p>

            <div className="mt-4 rounded-lg bg-amber-50 p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle
                  size={16}
                  className="mt-0.5 text-amber-600"
                />
                <div className="text-xs text-amber-800">
                  <p className="font-medium">
                    Please confirm the following:
                  </p>
                  <ul className="mt-1 list-inside list-disc space-y-0.5">
                    <li>
                      The justification letter has been reviewed
                    </li>
                    <li>
                      Patient information is accurate
                    </li>
                    <li>
                      CPT code {displayPA.cptCode} is correct
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            {submitMutation.isError && (
              <div className="mt-3 rounded bg-red-50 p-2 text-xs text-red-700">
                Submission failed. Please try again.
              </div>
            )}

            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => setShowSubmitModal(false)}
                className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
                disabled={submitMutation.isPending}
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitMutation.isPending}
                className="btn-primary flex items-center gap-2"
              >
                {submitMutation.isPending ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <Send size={16} />
                    Confirm Submission
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Helper Components ---

const CARC_TIPS: Record<string, { tip: string; winRate: number }> = {
  "CO-50": { tip: "Cite clinical guidelines. 71% overturn rate with strong clinical evidence.", winRate: 71 },
  "CO-4": { tip: "Verify CPT code accuracy. 85% overturn rate when coding is corrected.", winRate: 85 },
  "CO-197": { tip: "Provide authorization records with date proof. 62% overturn rate.", winRate: 62 },
  "CO-16": { tip: "Submit complete documentation package. 88% overturn rate.", winRate: 88 },
  "CO-119": { tip: "File medical exception with cost-avoidance data. 45% overturn rate.", winRate: 45 },
  "CO-96": { tip: "Check plan documents and state mandates. 38% overturn rate.", winRate: 38 },
  "PR-204": { tip: "File medical exception for unique clinical circumstances. 35% overturn rate.", winRate: 35 },
  "CO-170": { tip: "Update diagnosis codes and provide clinical rationale. 58% overturn rate.", winRate: 58 },
  "CO-151": { tip: "Document full scope and complexity of service. 52% overturn rate.", winRate: 52 },
  "CO-22": { tip: "Resolve coordination of benefits. 75% overturn rate.", winRate: 75 },
};

function CarcStrategyTip({ denialCode }: { denialCode: string | null }) {
  if (!denialCode) return null;
  const tip = CARC_TIPS[denialCode];
  if (!tip) return null;

  return (
    <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
      <AlertTriangle size={14} className="mt-0.5 flex-shrink-0 text-amber-500" />
      <p className="text-xs text-amber-800">
        <span className="font-semibold">{denialCode} denials:</span> {tip.tip}
      </p>
    </div>
  );
}

function DeadlineBadge({ deadline }: { deadline: string }) {
  const deadlineDate = new Date(deadline);
  const now = new Date();
  const daysRemaining = Math.max(0, Math.ceil((deadlineDate.getTime() - now.getTime()) / 86400000));

  const color = daysRemaining <= 3
    ? "bg-red-100 text-red-700 border-red-200"
    : daysRemaining <= 7
      ? "bg-amber-100 text-amber-700 border-amber-200"
      : "bg-slate-100 text-slate-700 border-slate-200";

  const formattedDate = deadlineDate.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
      <Clock size={10} />
      File by {formattedDate} ({daysRemaining} day{daysRemaining !== 1 ? "s" : ""})
    </span>
  );
}

// --- Clinical Extract Structured View ---

const CLINICAL_FIELD_LABELS: Record<string, string> = {
  diagnosis: "Primary Diagnosis",
  primaryDiagnosis: "Primary Diagnosis",
  severity: "Severity",
  symptoms: "Symptoms",
  duration: "Duration",
  functionalLimitation: "Functional Limitation",
  bmi: "BMI",
  age: "Age",
  imaging: "Imaging Results",
  labResults: "Lab Results",
  vitalSigns: "Vital Signs",
  allergies: "Allergies",
  comorbidities: "Comorbidities",
  smokingStatus: "Smoking Status",
  priorAuthorizations: "Prior Authorizations",
};

const TREATMENT_KEYS = [
  "conservativeTreatment",
  "priorTreatments",
  "treatments",
  "priorTherapy",
  "previousTreatments",
];

const MEDICATION_KEYS = [
  "medications",
  "currentMedications",
  "medicationList",
];

function isArrayOfStrings(val: unknown): val is string[] {
  return Array.isArray(val) && val.every((v) => typeof v === "string");
}

function isArrayOfObjects(val: unknown): val is Record<string, unknown>[] {
  return Array.isArray(val) && val.length > 0 && typeof val[0] === "object" && val[0] !== null;
}

function ExpandableSection({
  title,
  icon,
  expanded,
  onToggle,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-slate-100 last:border-b-0">
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-2 py-2.5 text-left text-sm font-medium text-slate-700 hover:text-slate-900 transition-colors"
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {icon}
        {title}
      </button>
      {expanded && <div className="pb-3 pl-7">{children}</div>}
    </div>
  );
}

function ClinicalExtractView({
  extract,
  showRawJson,
  onToggleRawJson,
  expandedSections,
  onToggleSection,
}: {
  extract: Record<string, unknown>;
  showRawJson: boolean;
  onToggleRawJson: () => void;
  expandedSections: Record<string, boolean>;
  onToggleSection: (key: string) => void;
}) {
  // Separate fields into categories
  const diagnosisFields: [string, unknown][] = [];
  const treatmentEntries: [string, unknown][] = [];
  const medicationEntries: [string, unknown][] = [];
  const otherFields: [string, unknown][] = [];

  for (const [key, value] of Object.entries(extract)) {
    if (TREATMENT_KEYS.includes(key)) {
      treatmentEntries.push([key, value]);
    } else if (MEDICATION_KEYS.includes(key)) {
      medicationEntries.push([key, value]);
    } else if (["diagnosis", "primaryDiagnosis", "severity", "symptoms", "duration", "functionalLimitation"].includes(key)) {
      diagnosisFields.push([key, value]);
    } else {
      otherFields.push([key, value]);
    }
  }

  return (
    <div className="space-y-1">
      {/* Diagnosis & Clinical Info */}
      {diagnosisFields.length > 0 && (
        <ExpandableSection
          title="Diagnosis & Clinical Information"
          icon={<Stethoscope size={14} className="text-blue-500" />}
          expanded={expandedSections.diagnosis ?? true}
          onToggle={() => onToggleSection("diagnosis")}
        >
          <div className="space-y-2">
            {diagnosisFields.map(([key, value]) => (
              <div key={key} className="flex flex-col sm:flex-row sm:gap-3">
                <span className="min-w-[160px] text-xs font-medium text-slate-500">
                  {CLINICAL_FIELD_LABELS[key] || key}
                </span>
                <span className="text-sm text-slate-800">
                  {value === null || value === undefined || value === "" ? (
                    <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-xs text-yellow-700">
                      Missing
                    </span>
                  ) : (
                    String(value)
                  )}
                </span>
              </div>
            ))}
          </div>
        </ExpandableSection>
      )}

      {/* Prior Treatments */}
      {treatmentEntries.length > 0 && (
        <ExpandableSection
          title="Prior Treatments"
          icon={<FileText size={14} className="text-emerald-500" />}
          expanded={expandedSections.treatments ?? true}
          onToggle={() => onToggleSection("treatments")}
        >
          {treatmentEntries.map(([key, value]) => {
            if (isArrayOfStrings(value)) {
              return (
                <table key={key} className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      <th className="py-1.5 text-left text-xs font-medium text-slate-500">Treatment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {value.map((item, i) => {
                      // Try to parse "Treatment x Duration" pattern
                      const parts = item.match(/^(.+?)\s+x\s+(.+)$/i);
                      return (
                        <tr key={i} className="border-b border-slate-50">
                          <td className="py-1.5 text-slate-700">
                            {parts ? (
                              <>
                                <span>{parts[1]}</span>
                                <span className="ml-2 text-xs text-slate-400">{parts[2]}</span>
                              </>
                            ) : (
                              item
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              );
            }
            if (isArrayOfObjects(value)) {
              const rows = value as Record<string, unknown>[];
              const cols = Object.keys(rows[0] ?? {});
              return (
                <table key={key} className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      {cols.map((col) => (
                        <th key={col} className="py-1.5 text-left text-xs font-medium capitalize text-slate-500">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={i} className="border-b border-slate-50">
                        {cols.map((col) => (
                          <td key={col} className="py-1.5 text-slate-700">
                            {row[col] === null || row[col] === undefined ? (
                              <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-xs text-yellow-700">
                                Missing
                              </span>
                            ) : (
                              String(row[col])
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            }
            return (
              <p key={key} className="text-sm text-slate-700">{String(value)}</p>
            );
          })}
        </ExpandableSection>
      )}

      {/* Medications */}
      {medicationEntries.length > 0 && (
        <ExpandableSection
          title="Medications"
          icon={<Pill size={14} className="text-purple-500" />}
          expanded={expandedSections.medications ?? true}
          onToggle={() => onToggleSection("medications")}
        >
          {medicationEntries.map(([key, value]) => {
            const meds = isArrayOfStrings(value) ? value : Array.isArray(value) ? value.map(String) : [String(value)];
            const colors = [
              "bg-blue-100 text-blue-700 border-blue-200",
              "bg-purple-100 text-purple-700 border-purple-200",
              "bg-emerald-100 text-emerald-700 border-emerald-200",
              "bg-amber-100 text-amber-700 border-amber-200",
              "bg-rose-100 text-rose-700 border-rose-200",
              "bg-cyan-100 text-cyan-700 border-cyan-200",
            ];
            return (
              <div key={key} className="flex flex-wrap gap-1.5">
                {meds.map((med, i) => (
                  <span
                    key={i}
                    className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${colors[i % colors.length]}`}
                  >
                    {med}
                  </span>
                ))}
              </div>
            );
          })}
        </ExpandableSection>
      )}

      {/* Other Fields */}
      {otherFields.length > 0 && (
        <ExpandableSection
          title="Additional Information"
          icon={<FileText size={14} className="text-slate-400" />}
          expanded={expandedSections.other ?? true}
          onToggle={() => onToggleSection("other")}
        >
          <div className="space-y-2">
            {otherFields.map(([key, value]) => (
              <div key={key} className="flex flex-col sm:flex-row sm:gap-3">
                <span className="min-w-[160px] text-xs font-medium text-slate-500">
                  {CLINICAL_FIELD_LABELS[key] || key.replace(/([A-Z])/g, " $1").replace(/^./, (s) => s.toUpperCase())}
                </span>
                <span className="text-sm text-slate-800">
                  {value === null || value === undefined || value === "" ? (
                    <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-xs text-yellow-700">
                      Missing
                    </span>
                  ) : typeof value === "object" ? (
                    <span className="font-mono text-xs text-slate-600">
                      {JSON.stringify(value)}
                    </span>
                  ) : (
                    String(value)
                  )}
                </span>
              </div>
            ))}
          </div>
        </ExpandableSection>
      )}

      {/* Raw JSON Toggle */}
      <div className="mt-4 border-t border-slate-200 pt-3">
        <button
          onClick={onToggleRawJson}
          className="flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-600 transition-colors"
        >
          <Code size={13} />
          {showRawJson ? "Hide Raw JSON" : "View Raw JSON"}
        </button>
        {showRawJson && (
          <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-green-400">
            {JSON.stringify(extract, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

// --- Letter Diff View ---

function LetterDiffView({ draft, final }: { draft: string; final: string }) {
  const editPct = computeEditPercentage(draft, final);
  const draftParas = draft.split(/\n\n+/);
  const finalParas = final.split(/\n\n+/);
  const maxParas = Math.max(draftParas.length, finalParas.length);

  return (
    <div className="space-y-3">
      {/* Edit percentage header */}
      <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
        <div className="flex-1">
          <span className="text-sm font-medium text-blue-800">
            {editPct}% modified from AI draft
          </span>
        </div>
        <div className="h-2 w-32 overflow-hidden rounded-full bg-blue-200">
          <div
            className="h-full rounded-full bg-blue-600 transition-all"
            style={{ width: `${Math.min(editPct, 100)}%` }}
          />
        </div>
      </div>

      {/* Split view */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            AI Draft (Original)
          </h3>
          <div className="max-h-[500px] overflow-y-auto rounded-lg bg-slate-50 p-3 font-mono text-xs text-slate-600 space-y-2">
            {Array.from({ length: maxParas }).map((_, i) => {
              const para = draftParas[i] ?? "";
              const otherPara = finalParas[i] ?? "";
              const matches = paragraphsMatch(para, otherPara);
              return (
                <p
                  key={i}
                  className={`whitespace-pre-wrap rounded px-2 py-1 ${
                    !matches && para
                      ? "bg-red-50 border-l-2 border-red-300"
                      : ""
                  }`}
                >
                  {para || <span className="italic text-slate-300">(removed)</span>}
                </p>
              );
            })}
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Human-Edited (Final)
          </h3>
          <div className="max-h-[500px] overflow-y-auto rounded-lg border border-green-200 bg-green-50/30 p-3 font-mono text-xs text-slate-700 space-y-2">
            {Array.from({ length: maxParas }).map((_, i) => {
              const para = finalParas[i] ?? "";
              const otherPara = draftParas[i] ?? "";
              const matches = paragraphsMatch(para, otherPara);
              return (
                <p
                  key={i}
                  className={`whitespace-pre-wrap rounded px-2 py-1 ${
                    !matches && para
                      ? "bg-green-100 border-l-2 border-green-400"
                      : ""
                  }`}
                >
                  {para || <span className="italic text-slate-300">(added)</span>}
                </p>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
