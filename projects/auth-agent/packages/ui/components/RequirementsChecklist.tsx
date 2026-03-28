"use client";

import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertTriangle,
  Info,
  FileText,
} from "lucide-react";

interface Criterion {
  id: string;
  category: string;
  description: string;
  required: boolean;
}

interface Requirements {
  payer_name: string;
  cpt_code: string;
  description: string;
  requires_pa: boolean;
  criteria: Criterion[];
  supporting_docs_required: string[];
  tips: string;
}

interface RequirementsChecklistProps {
  clinicalExtract: Record<string, unknown> | null;
  requirements: Requirements | null;
  compact?: boolean;
}

type MatchStatus = "met" | "missing" | "uncertain" | "pending";

function flattenExtractValues(obj: unknown): string {
  if (obj === null || obj === undefined) return "";
  if (typeof obj === "string") return obj.toLowerCase();
  if (typeof obj === "number" || typeof obj === "boolean")
    return String(obj).toLowerCase();
  if (Array.isArray(obj)) return obj.map(flattenExtractValues).join(" ");
  if (typeof obj === "object") {
    return Object.values(obj as Record<string, unknown>)
      .map(flattenExtractValues)
      .join(" ");
  }
  return "";
}

function getFieldText(
  extract: Record<string, unknown>,
  fields: string[]
): string {
  return fields
    .map((field) => {
      const value = extract[field];
      return value ? flattenExtractValues(value) : "";
    })
    .join(" ");
}

function matchCriterion(
  criterion: Criterion,
  extract: Record<string, unknown>
): MatchStatus {
  const category = criterion.category.toLowerCase();
  const desc = criterion.description.toLowerCase();

  if (category.includes("conservative") || desc.includes("conservative")) {
    const text = getFieldText(extract, [
      "prior_treatments",
      "treatment_history",
      "conservative_treatment",
    ]);
    if (!text) return "uncertain";
    const keywords = ["physical therapy", "pt", "conservative", "chiropractic", "exercise"];
    const found = keywords.some((kw) => text.includes(kw));
    return found ? "met" : "missing";
  }

  if (category.includes("medication") || desc.includes("medication")) {
    const text = getFieldText(extract, [
      "medications",
      "prior_treatments",
      "current_medications",
      "medication_history",
    ]);
    if (!text) return "uncertain";
    return text.length > 2 ? "met" : "missing";
  }

  if (
    category.includes("clinical_finding") ||
    category.includes("clinical finding") ||
    desc.includes("clinical finding")
  ) {
    const text = getFieldText(extract, [
      "symptoms",
      "physical_exam",
      "provider_assessment",
      "clinical_findings",
      "chief_complaint",
    ]);
    if (!text) return "uncertain";
    return text.length > 2 ? "met" : "missing";
  }

  if (category.includes("diagnostic") || desc.includes("diagnostic") || desc.includes("imaging")) {
    const text = getFieldText(extract, [
      "imaging_results",
      "lab_results",
      "diagnostic_results",
      "test_results",
    ]);
    if (!text) return "uncertain";
    return text.length > 2 ? "met" : "missing";
  }

  if (category.includes("documentation") || desc.includes("documentation")) {
    const relevantFields = [
      "diagnosis",
      "symptoms",
      "provider_assessment",
      "treatment_plan",
      "clinical_findings",
    ];
    const populated = relevantFields.filter((f) => {
      const val = extract[f];
      return val !== null && val !== undefined && val !== "";
    });
    if (populated.length >= 3) return "met";
    if (populated.length >= 1) return "uncertain";
    return "missing";
  }

  if (
    category.includes("functional") ||
    desc.includes("functional") ||
    desc.includes("assessment score")
  ) {
    const text = getFieldText(extract, [
      "functional_assessment",
      "functional_status",
      "assessment_scores",
      "physical_exam",
    ]);
    if (!text) return "uncertain";
    const keywords = ["score", "scale", "rating", "index", "oswestry", "vas", "sf-36"];
    const found = keywords.some((kw) => text.includes(kw));
    return found ? "met" : "uncertain";
  }

  if (
    category.includes("behavioral") ||
    category.includes("psychological") ||
    desc.includes("psychological") ||
    desc.includes("behavioral")
  ) {
    const text = getFieldText(extract, [
      "prior_treatments",
      "treatment_history",
      "psychological_evaluation",
      "behavioral_health",
    ]);
    if (!text) return "uncertain";
    const keywords = ["psychological", "behavioral", "mental health", "counseling", "therapy"];
    const found = keywords.some((kw) => text.includes(kw));
    return found ? "met" : "missing";
  }

  // Fallback: search the entire extract for keywords from the description
  const allText = flattenExtractValues(extract);
  const descWords = desc
    .split(/\s+/)
    .filter((w) => w.length > 4)
    .slice(0, 5);
  if (descWords.length === 0) return "uncertain";
  const matchCount = descWords.filter((w) => allText.includes(w)).length;
  if (matchCount >= Math.ceil(descWords.length * 0.6)) return "met";
  if (matchCount >= 1) return "uncertain";
  return "missing";
}

function checkSupportingDoc(
  docName: string,
  extract: Record<string, unknown>
): MatchStatus {
  const allText = flattenExtractValues(extract);
  const docLower = docName.toLowerCase();
  const keywords = docLower
    .split(/[\s_-]+/)
    .filter((w) => w.length > 3);
  const matchCount = keywords.filter((kw) => allText.includes(kw)).length;
  if (matchCount >= Math.ceil(keywords.length * 0.5)) return "met";
  if (matchCount >= 1) return "uncertain";
  return "missing";
}

const statusIcon: Record<MatchStatus, React.ReactNode> = {
  met: <CheckCircle2 className="h-5 w-5 shrink-0 text-green-500" />,
  missing: <XCircle className="h-5 w-5 shrink-0 text-red-500" />,
  uncertain: <HelpCircle className="h-5 w-5 shrink-0 text-yellow-500" />,
  pending: <HelpCircle className="h-5 w-5 shrink-0 text-slate-400" />,
};

export default function RequirementsChecklist({
  clinicalExtract,
  requirements,
  compact = false,
}: RequirementsChecklistProps) {
  if (!requirements) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-slate-200 bg-slate-50 px-6 py-10 text-center">
        <AlertTriangle className="mb-3 h-8 w-8 text-slate-400" />
        <p className="text-sm font-medium text-slate-600">
          No requirements loaded
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Select a payer and CPT code to view authorization criteria.
        </p>
      </div>
    );
  }

  const isPending = !clinicalExtract;

  const criteriaStatuses: { criterion: Criterion; status: MatchStatus }[] =
    requirements.criteria.map((criterion) => ({
      criterion,
      status: isPending
        ? "pending"
        : matchCriterion(criterion, clinicalExtract),
    }));

  const docStatuses: { doc: string; status: MatchStatus }[] =
    requirements.supporting_docs_required.map((doc) => ({
      doc,
      status: isPending
        ? "pending"
        : checkSupportingDoc(doc, clinicalExtract),
    }));

  const metCount = criteriaStatuses.filter((c) => c.status === "met").length;
  const totalCount = criteriaStatuses.length;
  const progressPct = totalCount > 0 ? Math.round((metCount / totalCount) * 100) : 0;

  return (
    <div className={compact ? "space-y-3" : "space-y-5"}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3
            className={`font-semibold text-slate-800 ${compact ? "text-sm" : "text-base"}`}
          >
            {requirements.payer_name}
          </h3>
          <p className="text-xs text-slate-500">
            CPT {requirements.cpt_code} &mdash; {requirements.description}
          </p>
        </div>
        {requirements.requires_pa && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700">
            <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
            PA Required
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div>
        <div className="mb-1.5 flex items-center justify-between text-xs text-slate-600">
          <span>
            {isPending
              ? "Pending clinical review"
              : `${metCount} of ${totalCount} criteria met`}
          </span>
          {!isPending && (
            <span className="font-medium">{progressPct}%</span>
          )}
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              progressPct === 100
                ? "bg-green-500"
                : progressPct >= 60
                  ? "bg-yellow-500"
                  : "bg-red-500"
            }`}
            style={{ width: isPending ? "0%" : `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Criteria checklist */}
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Criteria
        </h4>
        <ul className="space-y-1.5">
          {criteriaStatuses.map(({ criterion, status }) => (
            <li
              key={criterion.id}
              className="flex items-start gap-2.5 rounded-md border border-slate-100 bg-white px-3 py-2"
            >
              {statusIcon[status]}
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-700">
                  {criterion.description}
                </p>
                <p className="text-xs text-slate-400">{criterion.category}</p>
              </div>
              {criterion.required && (
                <span className="inline-flex shrink-0 items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                  Required
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      {/* Supporting documents */}
      {requirements.supporting_docs_required.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Supporting Documents
          </h4>
          <ul className="space-y-1.5">
            {docStatuses.map(({ doc, status }) => (
              <li
                key={doc}
                className="flex items-center gap-2.5 rounded-md border border-slate-100 bg-white px-3 py-2"
              >
                <FileText
                  className={`h-4 w-4 shrink-0 ${
                    status === "met"
                      ? "text-green-500"
                      : status === "missing"
                        ? "text-red-500"
                        : status === "uncertain"
                          ? "text-yellow-500"
                          : "text-slate-400"
                  }`}
                />
                <span className="text-sm text-slate-700">{doc}</span>
                {status === "met" && (
                  <CheckCircle2 className="ml-auto h-4 w-4 shrink-0 text-green-500" />
                )}
                {status === "missing" && (
                  <XCircle className="ml-auto h-4 w-4 shrink-0 text-red-500" />
                )}
                {(status === "uncertain" || status === "pending") && (
                  <HelpCircle className="ml-auto h-4 w-4 shrink-0 text-slate-400" />
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Tips info box */}
      {requirements.tips && (
        <div className="flex gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
          <div>
            <p className="text-xs font-medium text-blue-800">Tips</p>
            <p className="mt-0.5 text-xs text-blue-700">{requirements.tips}</p>
          </div>
        </div>
      )}

      {/* Pending notice */}
      {isPending && (
        <div className="flex gap-3 rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
          <p className="text-xs text-yellow-700">
            Clinical extract not yet available. All criteria are shown as
            pending review. Upload clinical documentation to begin matching.
          </p>
        </div>
      )}
    </div>
  );
}
