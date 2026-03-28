"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Search,
  Filter,
  ChevronDown,
  ChevronRight,
  FileCheck,
  AlertTriangle,
  Clock,
  Shield,
  Loader2,
} from "lucide-react";

// --- Types ---

interface PayerRequirement {
  payer_id: string;
  payer_name: string;
  cpt_code: string;
  description: string;
  requires_pa: boolean;
  criteria: {
    id: string;
    category: string;
    description: string;
    required: boolean;
  }[];
  supporting_docs_required: string[];
  clinical_guidelines: string[];
  avg_approval_days: number;
  denial_rate_estimate: number;
  common_denial_reasons: string[];
  tips: string;
}

interface Payer {
  id: string;
  name: string;
}

// --- API ---

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011";

async function fetchPayers(): Promise<Payer[]> {
  const res = await fetch(`${BASE_URL}/api/payers`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`API error: ${res.statusText}`);
  return res.json();
}

async function fetchPayerRequirements(): Promise<PayerRequirement[]> {
  const res = await fetch(`${BASE_URL}/api/payers/requirements`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`API error: ${res.statusText}`);
  return res.json();
}

// --- Fallback Data ---

const FALLBACK_PAYERS: Payer[] = [
  { id: "aetna-001", name: "Aetna" },
  { id: "uhc-001", name: "UnitedHealth" },
  { id: "cigna-001", name: "Cigna" },
  { id: "bcbs-001", name: "Blue Cross Blue Shield" },
  { id: "humana-001", name: "Humana" },
];

const FALLBACK_REQUIREMENTS: PayerRequirement[] = [
  {
    payer_id: "aetna-001",
    payer_name: "Aetna",
    cpt_code: "27447",
    description: "Total Knee Replacement (Arthroplasty)",
    requires_pa: true,
    criteria: [
      { id: "c1", category: "Clinical", description: "Documented failure of conservative treatment for 6+ weeks", required: true },
      { id: "c2", category: "Clinical", description: "Radiographic evidence of joint degeneration (Kellgren-Lawrence Grade 3+)", required: true },
      { id: "c3", category: "Functional", description: "Functional outcome measures (KOOS or WOMAC score below threshold)", required: true },
      { id: "c4", category: "Documentation", description: "BMI documented; optimization plan if BMI > 40", required: false },
    ],
    supporting_docs_required: [
      "Operative report or surgical plan",
      "X-ray or MRI reports within 6 months",
      "Physical therapy records documenting conservative treatment",
      "Functional assessment scores (KOOS/WOMAC)",
    ],
    clinical_guidelines: [
      "Aetna CPB 0645 - Total Knee Replacement",
      "AAOS Clinical Practice Guidelines for Knee OA",
    ],
    avg_approval_days: 5,
    denial_rate_estimate: 12,
    common_denial_reasons: [
      "Insufficient documentation of conservative treatment failure",
      "Missing functional outcome measures",
      "Incomplete radiographic evidence",
    ],
    tips: "Always include WOMAC/KOOS scores and at least 6 weeks of documented PT. Aetna peer-to-peer reviews are scheduled within 5 business days - request early if denial is likely.",
  },
  {
    payer_id: "uhc-001",
    payer_name: "UnitedHealth",
    cpt_code: "72148",
    description: "MRI Lumbar Spine Without Contrast",
    requires_pa: true,
    criteria: [
      { id: "c5", category: "Clinical", description: "Symptoms persisting for 6+ weeks despite conservative treatment", required: true },
      { id: "c6", category: "Clinical", description: "Red flag symptoms (progressive neurological deficit, cauda equina signs) for expedited review", required: false },
      { id: "c7", category: "Documentation", description: "Prior diagnostic steps documented (X-ray, clinical exam findings)", required: true },
      { id: "c8", category: "Clinical", description: "Failed trial of NSAIDs, physical therapy, or activity modification", required: true },
    ],
    supporting_docs_required: [
      "Office visit notes documenting symptoms and duration",
      "Prior imaging reports (X-ray)",
      "Physical therapy notes if applicable",
      "Medication history for the condition",
    ],
    clinical_guidelines: [
      "UHC Medical Policy - Advanced Imaging for Low Back Pain",
      "ACR Appropriateness Criteria - Low Back Pain",
    ],
    avg_approval_days: 7,
    denial_rate_estimate: 38,
    common_denial_reasons: [
      "Imaging requested before completing conservative treatment",
      "No documentation of prior diagnostic workup",
      "Clinical correlation not provided",
      "Symptoms duration less than required threshold",
    ],
    tips: "UHC has the highest denial rate for imaging. Always reference InterQual criteria explicitly in the letter. Document all prior diagnostic steps and include specific clinical correlation for the requested study.",
  },
  {
    payer_id: "cigna-001",
    payer_name: "Cigna",
    cpt_code: "29881",
    description: "Knee Arthroscopy with Meniscectomy",
    requires_pa: true,
    criteria: [
      { id: "c9", category: "Clinical", description: "MRI confirming meniscal tear with clinical correlation", required: true },
      { id: "c10", category: "Clinical", description: "Mechanical symptoms (locking, catching) documented", required: true },
      { id: "c11", category: "Clinical", description: "Failed 4+ weeks of conservative management", required: true },
      { id: "c12", category: "Documentation", description: "Patient age and activity level documented", required: false },
    ],
    supporting_docs_required: [
      "MRI report confirming meniscal pathology",
      "Office notes documenting mechanical symptoms",
      "Physical therapy records",
      "Surgical plan / indication statement",
    ],
    clinical_guidelines: [
      "Cigna Coverage Policy - Knee Arthroscopy",
      "AAOS Appropriate Use Criteria for Knee Arthroscopy",
    ],
    avg_approval_days: 4,
    denial_rate_estimate: 16,
    common_denial_reasons: [
      "Degenerative meniscal tear without mechanical symptoms",
      "Insufficient conservative treatment trial",
      "MRI findings inconsistent with clinical presentation",
    ],
    tips: "Cigna EviCore manages most surgical PAs. Submit through their portal for faster processing. Emphasize mechanical symptoms over pain alone - degenerative tears without locking/catching are frequently denied.",
  },
  {
    payer_id: "bcbs-001",
    payer_name: "Blue Cross Blue Shield",
    cpt_code: "43239",
    description: "Upper GI Endoscopy with Biopsy (EGD)",
    requires_pa: false,
    criteria: [
      { id: "c13", category: "Clinical", description: "Documented indication (GERD refractory to PPI, dysphagia, screening)", required: true },
      { id: "c14", category: "Documentation", description: "Prior medication trial documented if for GERD", required: false },
    ],
    supporting_docs_required: [
      "Office visit notes with indication",
      "Medication history if applicable",
    ],
    clinical_guidelines: [
      "BCBS Medical Policy - Gastrointestinal Endoscopy",
      "ACG Clinical Guidelines for GERD Management",
    ],
    avg_approval_days: 0,
    denial_rate_estimate: 8,
    common_denial_reasons: [
      "Repeat procedure without documented clinical change",
      "Screening EGD without qualifying risk factors",
    ],
    tips: "BCBS typically does not require PA for diagnostic EGD. However, verify which BCBS regional plan the patient carries as requirements vary. Submit via Availity for fastest processing when PA is needed.",
  },
  {
    payer_id: "humana-001",
    payer_name: "Humana",
    cpt_code: "64483",
    description: "Lumbar Epidural Steroid Injection (Transforaminal)",
    requires_pa: true,
    criteria: [
      { id: "c15", category: "Clinical", description: "Radiculopathy with imaging correlation (MRI or CT)", required: true },
      { id: "c16", category: "Clinical", description: "Failed conservative treatment (PT, medications) for 4+ weeks", required: true },
      { id: "c17", category: "Documentation", description: "Injection frequency within CMS guidelines (no more than 3 per region per year)", required: true },
      { id: "c18", category: "Clinical", description: "Documented pain score and functional limitations", required: true },
    ],
    supporting_docs_required: [
      "MRI or CT report showing pathology",
      "Office notes documenting radicular symptoms",
      "Prior injection dates and outcomes if applicable",
      "Physical therapy records",
      "Pain assessment scores",
    ],
    clinical_guidelines: [
      "Humana Medical Coverage Policy - Epidural Steroid Injections",
      "CMS Local Coverage Determination for ESI",
      "ASIPP Guidelines for Interventional Pain Management",
    ],
    avg_approval_days: 6,
    denial_rate_estimate: 24,
    common_denial_reasons: [
      "Exceeding frequency limitations",
      "No imaging correlation for injection level",
      "Insufficient documentation of conservative treatment",
      "Prior injection series without documented benefit",
    ],
    tips: "Humana requires CMS-compliant documentation for Medicare Advantage members. Always verify MA vs. commercial plan. Document prior injection outcomes - if previous series provided <50% relief, additional injections may be denied.",
  },
  {
    payer_id: "uhc-001",
    payer_name: "UnitedHealth",
    cpt_code: "27447",
    description: "Total Knee Replacement (Arthroplasty)",
    requires_pa: true,
    criteria: [
      { id: "c19", category: "Clinical", description: "Kellgren-Lawrence Grade 3 or 4 on weight-bearing radiographs", required: true },
      { id: "c20", category: "Clinical", description: "Failed 3+ months of conservative treatment including PT and medications", required: true },
      { id: "c21", category: "Functional", description: "Significant functional limitation documented (WOMAC, TUG test, or 6MWT)", required: true },
      { id: "c22", category: "Documentation", description: "Pre-surgical optimization: BMI < 40, HbA1c < 8%, tobacco cessation if applicable", required: true },
    ],
    supporting_docs_required: [
      "Weight-bearing AP and lateral knee radiographs",
      "3+ months of PT records",
      "Functional outcome assessments",
      "Pre-operative medical clearance",
      "BMI and HbA1c lab results",
    ],
    clinical_guidelines: [
      "UHC Medical Policy - Total Joint Replacement",
      "InterQual Criteria - Orthopedic Surgery",
      "AAOS Evidence-Based Guidelines for TKA",
    ],
    avg_approval_days: 8,
    denial_rate_estimate: 22,
    common_denial_reasons: [
      "BMI exceeds threshold without optimization plan",
      "Conservative treatment duration insufficient",
      "Missing pre-operative optimization labs",
      "Functional assessments not included",
    ],
    tips: "UHC strictly applies InterQual criteria - reference them explicitly. Ensure 3+ months (not 6 weeks) of conservative treatment is documented. Pre-surgical optimization labs are mandatory; submit HbA1c and BMI proactively.",
  },
];

// --- Component ---

export default function PayersPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPayer, setSelectedPayer] = useState<string>("all");
  const [selectedCpt, setSelectedCpt] = useState<string>("all");
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  const { data: payers } = useQuery({
    queryKey: ["payers"],
    queryFn: fetchPayers,
  });

  const { data: requirements, isLoading } = useQuery({
    queryKey: ["payer-requirements"],
    queryFn: fetchPayerRequirements,
  });

  const displayPayers = payers ?? FALLBACK_PAYERS;
  const displayRequirements = requirements ?? FALLBACK_REQUIREMENTS;

  const uniqueCpts = useMemo(() => {
    const cpts = Array.from(
      new Set(displayRequirements.map((r) => r.cpt_code))
    ).sort();
    return cpts;
  }, [displayRequirements]);

  const filtered = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return displayRequirements.filter((r) => {
      const matchesSearch =
        !q ||
        r.payer_name.toLowerCase().includes(q) ||
        r.cpt_code.includes(q) ||
        r.description.toLowerCase().includes(q);
      const matchesPayer =
        selectedPayer === "all" || r.payer_id === selectedPayer;
      const matchesCpt =
        selectedCpt === "all" || r.cpt_code === selectedCpt;
      return matchesSearch && matchesPayer && matchesCpt;
    });
  }, [displayRequirements, searchQuery, selectedPayer, selectedCpt]);

  function toggleCard(key: string) {
    setExpandedCards((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function denialRateColor(rate: number): string {
    if (rate < 15) return "bg-green-100 text-green-700";
    if (rate <= 30) return "bg-yellow-100 text-yellow-700";
    return "bg-red-100 text-red-700";
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1>Payer Requirements</h1>
        <p className="mt-1 text-sm text-slate-500">
          Search prior authorization requirements by payer and CPT code
        </p>
      </div>

      {/* Search & Filters */}
      <div className="card">
        <div className="flex flex-col gap-4 md:flex-row md:items-end">
          {/* Search */}
          <div className="flex-1">
            <label className="label">Search</label>
            <div className="relative">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                type="text"
                className="input pl-9"
                placeholder="Search by payer, CPT code, or description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>

          {/* Payer Filter */}
          <div className="w-full md:w-48">
            <label className="label flex items-center gap-1.5">
              <Filter size={12} className="text-slate-400" />
              Payer
            </label>
            <select
              className="input"
              value={selectedPayer}
              onChange={(e) => setSelectedPayer(e.target.value)}
            >
              <option value="all">All Payers</option>
              {displayPayers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* CPT Filter */}
          <div className="w-full md:w-48">
            <label className="label flex items-center gap-1.5">
              <Filter size={12} className="text-slate-400" />
              CPT Code
            </label>
            <select
              className="input"
              value={selectedCpt}
              onChange={(e) => setSelectedCpt(e.target.value)}
            >
              <option value="all">All CPT Codes</option>
              {uniqueCpts.map((cpt) => (
                <option key={cpt} value={cpt}>
                  {cpt}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <Search size={32} className="mx-auto mb-3 text-slate-300" />
          <p className="text-sm text-slate-500">
            No requirements found matching your search criteria.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            Showing {filtered.length} requirement{filtered.length !== 1 ? "s" : ""}
          </p>

          {filtered.map((req) => {
            const cardKey = `${req.payer_id}-${req.cpt_code}`;
            const isExpanded = expandedCards.has(cardKey);

            return (
              <div key={cardKey} className="card p-0 overflow-hidden">
                {/* Card Header */}
                <button
                  type="button"
                  className="flex w-full items-center gap-4 p-5 text-left transition-colors hover:bg-slate-50"
                  onClick={() => toggleCard(cardKey)}
                >
                  {isExpanded ? (
                    <ChevronDown size={18} className="flex-shrink-0 text-slate-400" />
                  ) : (
                    <ChevronRight size={18} className="flex-shrink-0 text-slate-400" />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-slate-800">
                        {req.payer_name}
                      </span>
                      <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600">
                        CPT {req.cpt_code}
                      </span>
                    </div>
                    <p className="mt-0.5 text-sm text-slate-500 truncate">
                      {req.description}
                    </p>
                  </div>

                  <div className="flex flex-shrink-0 items-center gap-3">
                    {/* PA Required Badge */}
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        req.requires_pa
                          ? "bg-red-50 text-red-700"
                          : "bg-green-50 text-green-700"
                      }`}
                    >
                      <Shield size={12} />
                      {req.requires_pa ? "PA Required" : "No PA"}
                    </span>

                    {/* Denial Rate */}
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${denialRateColor(
                        req.denial_rate_estimate
                      )}`}
                    >
                      {req.denial_rate_estimate}% denial
                    </span>

                    {/* Avg Days */}
                    <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                      <Clock size={12} />
                      {req.avg_approval_days}d
                    </span>
                  </div>
                </button>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="border-t border-slate-200 bg-slate-50/50 p-5">
                    <div className="grid gap-6 lg:grid-cols-2">
                      {/* Criteria Checklist */}
                      <div>
                        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-800">
                          <FileCheck size={14} className="text-primary-600" />
                          Authorization Criteria
                        </h3>
                        <ul className="space-y-2">
                          {req.criteria.map((c) => (
                            <li
                              key={c.id}
                              className="flex items-start gap-2 text-sm"
                            >
                              <span
                                className={`mt-1 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border text-[10px] ${
                                  c.required
                                    ? "border-primary-300 bg-primary-50 text-primary-600"
                                    : "border-slate-300 bg-white text-slate-400"
                                }`}
                              >
                                {c.required ? "\u2713" : "\u2013"}
                              </span>
                              <div>
                                <span className="text-slate-700">
                                  {c.description}
                                </span>
                                <span
                                  className={`ml-2 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                                    c.required
                                      ? "bg-primary-50 text-primary-600"
                                      : "bg-slate-100 text-slate-500"
                                  }`}
                                >
                                  {c.required ? "Required" : "Recommended"}
                                </span>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Supporting Docs */}
                      <div>
                        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-800">
                          <FileCheck size={14} className="text-slate-500" />
                          Supporting Documents Required
                        </h3>
                        <ul className="space-y-1.5">
                          {req.supporting_docs_required.map((doc, i) => (
                            <li
                              key={i}
                              className="flex items-start gap-2 text-sm text-slate-600"
                            >
                              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-400" />
                              {doc}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Clinical Guidelines */}
                      <div>
                        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-800">
                          <Shield size={14} className="text-blue-500" />
                          Clinical Guidelines Referenced
                        </h3>
                        <ul className="space-y-1.5">
                          {req.clinical_guidelines.map((gl, i) => (
                            <li
                              key={i}
                              className="flex items-start gap-2 text-sm text-slate-600"
                            >
                              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-400" />
                              {gl}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Common Denial Reasons */}
                      <div>
                        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-800">
                          <AlertTriangle size={14} className="text-red-500" />
                          Common Denial Reasons
                        </h3>
                        <ul className="space-y-1.5">
                          {req.common_denial_reasons.map((reason, i) => (
                            <li
                              key={i}
                              className="flex items-start gap-2 text-sm text-slate-600"
                            >
                              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-red-400" />
                              {reason}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* Tips */}
                    {req.tips && (
                      <div className="mt-5 rounded-lg border border-yellow-200 bg-yellow-50 p-4">
                        <h3 className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-yellow-800">
                          <AlertTriangle size={14} />
                          Tips
                        </h3>
                        <p className="text-sm text-yellow-700">{req.tips}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
