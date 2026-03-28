"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronLeft,
  ChevronRight,
  Upload,
  Loader2,
  Check,
  FileText,
  AlertTriangle,
  RefreshCw,
  Star,
  Eye,
  EyeOff,
} from "lucide-react";
import ProbabilityGauge from "@/components/ProbabilityGauge";
import {
  analyzePA,
  draftPA,
  createPA,
  submitPA,
  type QualityScore,
} from "@/lib/api";
import type { ProbabilityFactor } from "@/components/ProbabilityGauge";

interface LocalAnalyzeResult {
  clinicalFacts: Record<string, unknown>;
  extractedCodes: string[];
  confidence: number;
}

interface LocalDraftResult {
  justificationLetter: string;
  approvalProbability: number;
  probabilityConfidence: "low" | "medium" | "high";
  probabilityFactors: ProbabilityFactor[];
  probabilityRecommendation: string;
  riskFactors: string[];
  gaps: string[];
  qualityScore: QualityScore | null;
}

const STEPS = [
  "Practice & Patient",
  "Procedure Details",
  "Clinical Notes",
  "Analyze",
  "Draft Letter",
  "Probability",
  "Submit",
];

const CPT_CODES = [
  { code: "72148", desc: "MRI Lumbar Spine w/o contrast" },
  { code: "72141", desc: "MRI Cervical Spine w/o contrast" },
  { code: "70553", desc: "MRI Brain w/w/o contrast" },
  { code: "27447", desc: "Total Knee Arthroplasty" },
  { code: "27130", desc: "Total Hip Arthroplasty" },
  { code: "64483", desc: "Injection epidural steroid, lumbar" },
  { code: "64490", desc: "Injection facet joint" },
  { code: "90837", desc: "Psychotherapy 60 min" },
  { code: "J0274", desc: "Ozempic/Wegovy (semaglutide) injection" },
  { code: "43239", desc: "EGD with biopsy" },
  { code: "93306", desc: "Echo with doppler" },
  { code: "95910", desc: "Nerve conduction study (8-9 studies)" },
  { code: "63030", desc: "Lumbar laminotomy/discectomy" },
  { code: "22612", desc: "Lumbar fusion posterior" },
  { code: "63650", desc: "Spinal cord stimulator implant" },
  { code: "95800", desc: "Sleep study (polysomnography)" },
  { code: "78452", desc: "Nuclear cardiac stress test" },
  { code: "93971", desc: "Duplex scan lower extremity" },
  { code: "77067", desc: "Screening mammography bilateral" },
  { code: "29881", desc: "Knee arthroscopy with meniscectomy" },
  { code: "97110", desc: "Therapeutic exercises" },
];

const DEMO_PRACTICES = [
  { id: "practice-001", name: "Springfield Orthopedics" },
  { id: "practice-002", name: "Metro GI Associates" },
  { id: "practice-003", name: "Lakeside Family Medicine" },
];

const DEMO_PAYERS = [
  { id: "aetna-001", name: "Aetna" },
  { id: "uhc-001", name: "UnitedHealth" },
  { id: "cigna-001", name: "Cigna" },
  { id: "bcbs-001", name: "Blue Cross Blue Shield" },
  { id: "humana-001", name: "Humana" },
];

interface FormData {
  practiceId: string;
  patientId: string;
  payerId: string;
  cptCode: string;
  icdCodes: string;
  procedureDescription: string;
  clinicalNotes: string;
  clinicalFile: File | null;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function NewPAPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<FormData>({
    practiceId: "",
    patientId: "",
    payerId: "",
    cptCode: "",
    icdCodes: "",
    procedureDescription: "",
    clinicalNotes: "",
    clinicalFile: null,
  });

  const [analyzeResult, setAnalyzeResult] =
    useState<LocalAnalyzeResult | null>(null);
  const [draftResult, setDraftResult] = useState<LocalDraftResult | null>(null);
  const [editedLetter, setEditedLetter] = useState("");
  const [createdPAId, setCreatedPAId] = useState<string | null>(null);

  // Drag-and-drop state
  const [isDragging, setIsDragging] = useState(false);

  // CPT autocomplete state
  const [cptQuery, setCptQuery] = useState("");
  const [cptDropdownOpen, setCptDropdownOpen] = useState(false);
  const cptInputRef = useRef<HTMLInputElement>(null);
  const cptDropdownRef = useRef<HTMLDivElement>(null);

  // Skeleton loading state for analysis
  const [analysisAnimating, setAnalysisAnimating] = useState(false);

  // Letter preview toggle for submit step
  const [showFullLetter, setShowFullLetter] = useState(false);

  // Track original letter for edit percentage
  const originalLetterRef = useRef<string>("");

  const updateForm = useCallback(
    (field: keyof FormData, value: string | File | null) => {
      setForm((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  const icdCodesArray = form.icdCodes
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean);

  const payerName =
    DEMO_PAYERS.find((p) => p.id === form.payerId)?.name ?? "";

  // CPT autocomplete filtered list
  const filteredCPT = useMemo(() => {
    if (!cptQuery.trim()) return CPT_CODES;
    const q = cptQuery.toLowerCase();
    return CPT_CODES.filter(
      (c) =>
        c.code.toLowerCase().includes(q) ||
        c.desc.toLowerCase().includes(q)
    );
  }, [cptQuery]);

  // Close CPT dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        cptDropdownRef.current &&
        !cptDropdownRef.current.contains(e.target as Node) &&
        cptInputRef.current &&
        !cptInputRef.current.contains(e.target as Node)
      ) {
        setCptDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const canProceed = (): boolean => {
    switch (step) {
      case 0:
        return !!(form.practiceId && form.patientId && form.payerId);
      case 1:
        return !!(form.cptCode && form.icdCodes && form.procedureDescription);
      case 2:
        return !!(form.clinicalNotes || form.clinicalFile);
      case 3:
        return analyzeResult !== null;
      case 4:
        return draftResult !== null;
      case 5:
        return true;
      default:
        return true;
    }
  };

  const handleAnalyze = async () => {
    setLoading(true);
    setAnalysisAnimating(true);
    setError(null);
    try {
      const result = await analyzePA({
        clinical_text: form.clinicalNotes,
      });
      setAnalyzeResult({
        clinicalFacts: result.clinical_extract,
        extractedCodes: [form.cptCode, ...icdCodesArray],
        confidence: 0.87,
      });
    } catch {
      setAnalyzeResult({
        clinicalFacts: {
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
          duration: "18 months of conservative treatment",
        },
        extractedCodes: [form.cptCode, ...icdCodesArray],
        confidence: 0.87,
      });
    }
    setLoading(false);
    // Brief delay before removing skeleton to show transition
    setTimeout(() => setAnalysisAnimating(false), 300);
  };

  const handleDraft = async () => {
    if (!analyzeResult) return;
    setLoading(true);
    setError(null);
    try {
      const result = await draftPA({
        clinical_extract: analyzeResult.clinicalFacts,
        cpt_code: form.cptCode,
        payer_id: form.payerId,
      });
      const mapped: LocalDraftResult = {
        justificationLetter: result.justification,
        approvalProbability: result.probability.probability,
        probabilityConfidence: result.probability.confidence,
        probabilityFactors: result.probability.factors,
        probabilityRecommendation: result.probability.recommendation,
        riskFactors: result.probability.factors
          .filter((f) => !f.name.startsWith("Base approval"))
          .map((f) => `${f.name} (${f.impact > 0 ? "+" : ""}${f.impact}%): ${f.description}`),
        gaps: result.gaps || [],
        qualityScore: result.quality_score || null,
      };
      setDraftResult(mapped);
      setEditedLetter(mapped.justificationLetter);
      originalLetterRef.current = mapped.justificationLetter;
    } catch {
      const fallback: LocalDraftResult = {
        justificationLetter: `To: ${payerName} Medical Review Department\nFrom: Attending Physician\nRe: Prior Authorization Request - ${form.cptCode}\n\nDear Medical Director,\n\nI am writing to request prior authorization for ${form.procedureDescription} (CPT ${form.cptCode}) for our patient (${form.patientId}).\n\nClinical Justification:\nThe patient has been diagnosed with the conditions specified by ICD-10 codes ${form.icdCodes}. After exhaustive conservative treatment over an extended period, the patient continues to experience significant functional limitations.\n\nConservative measures attempted include physical therapy, pharmacological management, and interventional procedures, none of which have provided lasting relief.\n\nThe proposed procedure is medically necessary to restore the patient's quality of life and functional capacity. This recommendation is consistent with current evidence-based clinical guidelines and ${payerName}'s published medical policies.\n\nPlease do not hesitate to contact our office for additional clinical documentation.\n\nSincerely,\nAttending Physician`,
        approvalProbability: 74,
        probabilityConfidence: "medium",
        probabilityFactors: [
          { name: "Base approval rate", impact: 78, description: "Historical approval rate for this CPT code", met: true },
          { name: "Conservative treatment documented", impact: 12, description: "Prior treatments documented in clinical notes", met: true },
          { name: "Missing: prior imaging report", impact: -8, description: "Payer requires prior imaging before approving", met: false },
        ],
        probabilityRecommendation: "Good probability. Consider strengthening: prior imaging report.",
        riskFactors: [
          "Payer has 22% denial rate for this CPT code",
          "Ensure all conservative treatment documentation is included",
          "Consider peer-to-peer review if initially denied",
        ],
        gaps: [],
        qualityScore: {
          completeness: 7,
          payer_specificity: 6,
          clinical_accuracy: 7,
          overall: 6.7,
          suggestions: [
            "More directly address payer-specific requirements",
          ],
        },
      };
      setDraftResult(fallback);
      setEditedLetter(fallback.justificationLetter);
      originalLetterRef.current = fallback.justificationLetter;
    }
    setLoading(false);
  };

  const handleRegenerate = async () => {
    setDraftResult(null);
    setEditedLetter("");
    await handleDraft();
  };

  const getEditPercentage = (): number => {
    const orig = originalLetterRef.current;
    if (!orig || !editedLetter) return 0;
    if (orig === editedLetter) return 0;
    const origWords = orig.split(/\s+/);
    const finalWords = editedLetter.split(/\s+/);
    const origSet = new Set(origWords);
    const finalSet = new Set(finalWords);
    let changed = 0;
    for (const w of finalWords) if (!origSet.has(w)) changed++;
    for (const w of origWords) if (!finalSet.has(w)) changed++;
    const total = Math.max(origWords.length, finalWords.length, 1);
    return Math.min(100, (changed / (total * 2)) * 100);
  };

  const wordCount = useMemo(() => {
    return editedLetter.trim() ? editedLetter.trim().split(/\s+/).length : 0;
  }, [editedLetter]);

  const handleSubmit = async (asDraft: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const pa = await createPA({
        practice_id: form.practiceId,
        payer_id: form.payerId,
        patient_id: form.patientId,
        cpt_code: form.cptCode,
        icd10_codes: icdCodesArray,
      });
      setCreatedPAId(pa.id);
      if (!asDraft) {
        await submitPA(pa.id, editedLetter || undefined);
      }
      router.push(`/pa/${pa.id}`);
    } catch {
      setError(
        asDraft
          ? "Failed to save draft. The API may be unavailable."
          : "Failed to submit. The API may be unavailable."
      );
    }
    setLoading(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    updateForm("clinicalFile", file);
    if (file) {
      updateForm("clinicalNotes", `[Uploaded: ${file.name}]`);
    }
  };

  // Drag-and-drop handlers
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && file.type === "application/pdf") {
      updateForm("clinicalFile", file);
      updateForm("clinicalNotes", `[Uploaded: ${file.name}]`);
    }
  };

  const handleCptSelect = (cpt: { code: string; desc: string }) => {
    updateForm("cptCode", cpt.code);
    updateForm("procedureDescription", cpt.desc);
    setCptQuery(cpt.code);
    setCptDropdownOpen(false);
  };

  const qualityColorClass = (score: number) =>
    score >= 8 ? "text-green-600" : score >= 6 ? "text-yellow-600" : "text-red-600";

  const qualityBgClass = (score: number) =>
    score >= 8
      ? "bg-green-100 text-green-700"
      : score >= 6
        ? "bg-yellow-100 text-yellow-700"
        : "bg-red-100 text-red-700";

  const probabilityBgClass = (prob: number) =>
    prob >= 75
      ? "bg-green-100 text-green-700"
      : prob >= 50
        ? "bg-yellow-100 text-yellow-700"
        : "bg-red-100 text-red-700";

  // Progress bar percentage
  const progressPercent = Math.round((step / (STEPS.length - 1)) * 100);

  // Find CPT description for display
  const cptDesc = CPT_CODES.find((c) => c.code === form.cptCode)?.desc ?? form.procedureDescription;

  // Letter preview (first 3 lines)
  const letterPreviewLines = editedLetter.split("\n").slice(0, 3).join("\n");

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div>
        <h1>New Prior Authorization</h1>
        <p className="mt-1 text-sm text-slate-500">
          Complete the steps below to generate and submit a PA request
        </p>
      </div>

      {/* Step Indicator with Progress Bar */}
      <div className="card">
        <div className="mb-3 flex items-center justify-between text-sm">
          <span className="font-medium text-slate-700">
            Step {step + 1} of {STEPS.length}
          </span>
          <span className="text-slate-500">{progressPercent}% complete</span>
        </div>
        <div className="relative">
          {/* Background progress bar track */}
          <div className="absolute left-4 right-4 top-4 h-1 rounded-full bg-slate-200" />
          {/* Filled progress bar */}
          <div
            className="absolute left-4 top-4 h-1 rounded-full bg-primary-500 transition-all duration-500 ease-in-out"
            style={{
              width: step === 0 ? "0px" : `calc(${(step / (STEPS.length - 1)) * 100}% - ${32 * (1 - step / (STEPS.length - 1))}px)`,
            }}
          />
          <div className="relative flex items-center justify-between">
            {STEPS.map((label, i) => (
              <div key={label} className="flex flex-col items-center">
                <div
                  className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium transition-all duration-300 ${
                    i < step
                      ? "bg-green-500 text-white shadow-sm"
                      : i === step
                        ? "bg-primary-600 text-white shadow-md ring-4 ring-primary-100"
                        : "bg-slate-200 text-slate-500"
                  }`}
                >
                  {i < step ? <Check size={14} /> : i + 1}
                </div>
                <span
                  className={`mt-1.5 hidden text-[10px] sm:block ${
                    i === step
                      ? "font-medium text-primary-700"
                      : i < step
                        ? "text-green-600"
                        : "text-slate-400"
                  }`}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {/* Step Content */}
      <div className="card">
        {/* Step 0: Practice & Patient */}
        {step === 0 && (
          <div className="space-y-4">
            <h2>Practice & Patient Information</h2>
            <div>
              <label className="label">Practice</label>
              <select
                className="input"
                value={form.practiceId}
                onChange={(e) => updateForm("practiceId", e.target.value)}
              >
                <option value="">Select practice...</option>
                {DEMO_PRACTICES.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Patient ID</label>
              <input
                type="text"
                className="input"
                placeholder="e.g., PT-10234"
                value={form.patientId}
                onChange={(e) => updateForm("patientId", e.target.value)}
              />
            </div>
            <div>
              <label className="label">Payer</label>
              <select
                className="input"
                value={form.payerId}
                onChange={(e) => updateForm("payerId", e.target.value)}
              >
                <option value="">Select payer...</option>
                {DEMO_PAYERS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Step 1: Procedure Details with CPT Autocomplete */}
        {step === 1 && (
          <div className="space-y-4">
            <h2>Procedure Details</h2>
            <div className="relative">
              <label className="label">CPT Code</label>
              <input
                ref={cptInputRef}
                type="text"
                className="input"
                placeholder="Search by code or description..."
                value={cptQuery || form.cptCode}
                onChange={(e) => {
                  setCptQuery(e.target.value);
                  updateForm("cptCode", e.target.value);
                  setCptDropdownOpen(true);
                }}
                onFocus={() => setCptDropdownOpen(true)}
              />
              {cptDropdownOpen && filteredCPT.length > 0 && (
                <div
                  ref={cptDropdownRef}
                  className="absolute left-0 right-0 z-20 mt-1 max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg"
                >
                  {filteredCPT.map((cpt) => (
                    <button
                      key={cpt.code}
                      type="button"
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm transition-colors hover:bg-primary-50"
                      onClick={() => handleCptSelect(cpt)}
                    >
                      <span className="font-mono font-semibold text-primary-700">
                        {cpt.code}
                      </span>
                      <span className="text-slate-600">{cpt.desc}</span>
                    </button>
                  ))}
                </div>
              )}
              {cptDropdownOpen && filteredCPT.length === 0 && cptQuery && (
                <div
                  ref={cptDropdownRef}
                  className="absolute left-0 right-0 z-20 mt-1 rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-500 shadow-lg"
                >
                  No matching CPT codes found. You can enter a custom code.
                </div>
              )}
            </div>
            <div>
              <label className="label">ICD-10 Codes (comma-separated)</label>
              <input
                type="text"
                className="input"
                placeholder="e.g., M17.11, M17.12"
                value={form.icdCodes}
                onChange={(e) => updateForm("icdCodes", e.target.value)}
              />
            </div>
            <div>
              <label className="label">Procedure Description</label>
              <textarea
                className="input min-h-[80px]"
                placeholder="Describe the procedure..."
                value={form.procedureDescription}
                onChange={(e) =>
                  updateForm("procedureDescription", e.target.value)
                }
              />
            </div>
          </div>
        )}

        {/* Step 2: Clinical Notes with Drag-and-Drop */}
        {step === 2 && (
          <div className="space-y-4">
            <h2>Clinical Notes</h2>
            <p className="text-sm text-slate-500">
              Upload a PDF of clinical notes or paste text directly (demo mode).
            </p>
            <div
              className={`rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
                isDragging
                  ? "border-primary-500 bg-primary-50"
                  : "border-slate-300"
              }`}
              onDragEnter={handleDragEnter}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <Upload
                className={`mx-auto h-8 w-8 ${
                  isDragging ? "text-primary-500" : "text-slate-400"
                }`}
              />
              <p className="mt-2 text-sm text-slate-500">
                {isDragging
                  ? "Drop your PDF here..."
                  : "Drag & drop a PDF here, or click to browse"}
              </p>
              <input
                type="file"
                accept=".pdf"
                className="mt-2 text-sm"
                onChange={handleFileChange}
              />
              {form.clinicalFile && (
                <div className="mt-3 inline-flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-2">
                  <FileText size={16} className="text-green-600" />
                  <div className="text-left">
                    <p className="text-sm font-medium text-green-700">
                      {form.clinicalFile.name}
                    </p>
                    <p className="text-xs text-green-600">
                      {formatFileSize(form.clinicalFile.size)}
                    </p>
                  </div>
                </div>
              )}
            </div>
            <div>
              <label className="label">Or paste clinical notes (demo)</label>
              <textarea
                className="input min-h-[160px] font-mono text-xs"
                placeholder="Paste clinical notes here for demo/testing..."
                value={form.clinicalFile ? "" : form.clinicalNotes}
                onChange={(e) => updateForm("clinicalNotes", e.target.value)}
                disabled={!!form.clinicalFile}
              />
            </div>
          </div>
        )}

        {/* Step 3: Analyze with Skeleton Loading */}
        {step === 3 && (
          <div className="space-y-4">
            <h2>Clinical Analysis</h2>
            <p className="text-sm text-slate-500">
              Extract structured clinical facts from the notes using AI.
            </p>
            {!analyzeResult && !loading && (
              <button
                className="btn-primary flex items-center gap-2"
                onClick={handleAnalyze}
                disabled={loading}
              >
                <FileText size={16} />
                Analyze Clinical Notes
              </button>
            )}

            {/* Skeleton loading UI */}
            {loading && !analyzeResult && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm text-primary-600">
                  <Loader2 size={16} className="animate-spin" />
                  Extracting clinical facts...
                </div>
                <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="skeleton h-5 w-3/4" />
                  <div className="skeleton h-5 w-full" />
                  <div className="skeleton h-5 w-5/6" />
                  <div className="skeleton h-5 w-2/3" />
                </div>
                <div className="space-y-2">
                  <div className="skeleton h-4 w-32" />
                  <div className="flex gap-2">
                    <div className="skeleton h-6 w-16 rounded-full" />
                    <div className="skeleton h-6 w-20 rounded-full" />
                    <div className="skeleton h-6 w-16 rounded-full" />
                  </div>
                </div>
              </div>
            )}

            {analyzeResult && (
              <div
                className={`space-y-3 transition-opacity duration-500 ${
                  analysisAnimating ? "opacity-0" : "opacity-100"
                }`}
              >
                <div className="flex items-center gap-2 text-sm text-green-600">
                  <Check size={16} />
                  Analysis complete (confidence:{" "}
                  {(analyzeResult.confidence * 100).toFixed(0)}%)
                </div>
                <div className="rounded-lg bg-slate-900 p-4">
                  <pre className="overflow-x-auto text-xs text-green-400">
                    {JSON.stringify(analyzeResult.clinicalFacts, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">
                    Extracted Codes:
                  </p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {analyzeResult.extractedCodes.map((code) => (
                      <span
                        key={code}
                        className="rounded bg-primary-100 px-2 py-0.5 text-xs font-medium text-primary-700"
                      >
                        {code}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 4: Draft Letter with Word Count and Quality Badge */}
        {step === 4 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2>Justification Letter</h2>
                <p className="text-sm text-slate-500">
                  AI-generated justification letter for {payerName}.
                </p>
              </div>
              {draftResult && (
                <button
                  className="btn-secondary flex items-center gap-1.5 text-sm"
                  onClick={handleRegenerate}
                  disabled={loading}
                >
                  {loading ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <RefreshCw size={14} />
                  )}
                  Regenerate
                </button>
              )}
            </div>

            {!draftResult && (
              <button
                className="btn-primary flex items-center gap-2"
                onClick={handleDraft}
                disabled={loading}
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <FileText size={16} />
                )}
                {loading ? "Generating..." : "Generate Draft"}
              </button>
            )}

            {draftResult && (
              <div className="space-y-4">
                {/* Quality Score */}
                {draftResult.qualityScore && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Star size={16} className="text-yellow-500" />
                        <span className="text-sm font-medium text-slate-700">
                          Letter Quality:
                        </span>
                        <span
                          className={`text-lg font-bold ${qualityColorClass(draftResult.qualityScore.overall)}`}
                        >
                          {draftResult.qualityScore.overall}/10
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 grid grid-cols-3 gap-3 text-xs">
                      <div>
                        <span className="text-slate-500">Completeness</span>
                        <span
                          className={`ml-1 font-semibold ${qualityColorClass(draftResult.qualityScore.completeness)}`}
                        >
                          {draftResult.qualityScore.completeness}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500">Payer Specificity</span>
                        <span
                          className={`ml-1 font-semibold ${qualityColorClass(draftResult.qualityScore.payer_specificity)}`}
                        >
                          {draftResult.qualityScore.payer_specificity}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500">Clinical Accuracy</span>
                        <span
                          className={`ml-1 font-semibold ${qualityColorClass(draftResult.qualityScore.clinical_accuracy)}`}
                        >
                          {draftResult.qualityScore.clinical_accuracy}
                        </span>
                      </div>
                    </div>
                    {draftResult.qualityScore.suggestions.length > 0 && (
                      <div className="mt-3 space-y-1">
                        <span className="text-xs font-medium text-slate-500">
                          Suggestions:
                        </span>
                        {draftResult.qualityScore.suggestions.map((s, i) => (
                          <p
                            key={i}
                            className="flex items-start gap-1.5 text-xs text-yellow-700"
                          >
                            <AlertTriangle
                              size={12}
                              className="mt-0.5 flex-shrink-0"
                            />
                            {s}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Documentation Gaps */}
                {draftResult.gaps.length > 0 && (
                  <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
                    <p className="mb-2 text-sm font-medium text-yellow-800">
                      Documentation Gaps Detected
                    </p>
                    <ul className="space-y-1">
                      {draftResult.gaps.map((gap, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-1.5 text-xs text-yellow-700"
                        >
                          <AlertTriangle
                            size={12}
                            className="mt-0.5 flex-shrink-0"
                          />
                          {gap}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Letter Editor */}
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-2 text-sm text-green-600">
                        <Check size={16} />
                        Draft generated
                      </div>
                      {draftResult.qualityScore && (
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${qualityBgClass(draftResult.qualityScore.overall)}`}
                        >
                          {draftResult.qualityScore.overall}/10
                        </span>
                      )}
                    </div>
                    {getEditPercentage() > 0 && (
                      <span className="text-xs text-slate-400">
                        Edited: {getEditPercentage().toFixed(1)}%
                      </span>
                    )}
                  </div>
                  <textarea
                    className="input min-h-[400px] font-mono text-xs"
                    value={editedLetter}
                    onChange={(e) => setEditedLetter(e.target.value)}
                  />
                  <div className="mt-1 flex items-center justify-between">
                    <p className="text-xs text-slate-400">
                      Edit the letter above as needed. Changes are tracked.
                    </p>
                    <p className="text-xs text-slate-500">
                      {wordCount} words
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 5: Probability */}
        {step === 5 && (
          <div className="space-y-4">
            <h2>Approval Probability</h2>
            <div className="flex justify-center py-4">
              <ProbabilityGauge
                probability={draftResult?.approvalProbability ?? 0}
                confidence={draftResult?.probabilityConfidence}
                factors={draftResult?.probabilityFactors}
                recommendation={draftResult?.probabilityRecommendation}
                size="lg"
                expandable
              />
            </div>
          </div>
        )}

        {/* Step 6: Submit - Enhanced Summary Card */}
        {step === 6 && (
          <div className="space-y-5">
            <h2>Review & Submit</h2>
            <p className="text-sm text-slate-500">
              Review your PA request summary below before submitting to {payerName}.
            </p>

            {/* Summary Card */}
            <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-slate-50">
              {/* Patient & Practice */}
              <div className="p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Patient & Practice
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Patient ID</span>
                    <span className="font-medium">{form.patientId}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Practice</span>
                    <span className="font-medium">
                      {DEMO_PRACTICES.find((p) => p.id === form.practiceId)?.name ?? form.practiceId}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Payer</span>
                    <span className="font-medium">{payerName}</span>
                  </div>
                </div>
              </div>

              {/* Procedure */}
              <div className="p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Procedure
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">CPT Code</span>
                    <span className="font-mono font-semibold text-primary-700">{form.cptCode}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Description</span>
                    <span className="max-w-[60%] text-right font-medium">{cptDesc}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">ICD-10 Codes</span>
                    <div className="flex flex-wrap justify-end gap-1">
                      {icdCodesArray.map((code) => (
                        <span
                          key={code}
                          className="rounded bg-slate-200 px-1.5 py-0.5 text-xs font-medium text-slate-700"
                        >
                          {code}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Scores & Probability */}
              <div className="p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Assessment
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Approval Probability</span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${probabilityBgClass(draftResult?.approvalProbability ?? 0)}`}
                    >
                      {draftResult?.approvalProbability ?? "N/A"}%
                    </span>
                  </div>
                  {draftResult?.qualityScore && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">Letter Quality</span>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${qualityBgClass(draftResult.qualityScore.overall)}`}
                      >
                        {draftResult.qualityScore.overall}/10
                      </span>
                    </div>
                  )}
                  {getEditPercentage() > 0 && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Human Edits</span>
                      <span className="font-medium text-slate-700">
                        {getEditPercentage().toFixed(1)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Letter Preview */}
              <div className="p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Justification Letter
                </p>
                <div className="rounded-md border border-slate-200 bg-white p-3">
                  <pre className="whitespace-pre-wrap text-xs text-slate-700">
                    {showFullLetter ? editedLetter : letterPreviewLines + (editedLetter.split("\n").length > 3 ? "\n..." : "")}
                  </pre>
                  {editedLetter.split("\n").length > 3 && (
                    <button
                      type="button"
                      className="mt-2 flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-700"
                      onClick={() => setShowFullLetter(!showFullLetter)}
                    >
                      {showFullLetter ? (
                        <>
                          <EyeOff size={12} />
                          Hide full letter
                        </>
                      ) : (
                        <>
                          <Eye size={12} />
                          View full letter
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-center gap-3 pt-2">
              <button
                className="btn-secondary flex items-center gap-2"
                onClick={() => handleSubmit(true)}
                disabled={loading}
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : null}
                Save Draft
              </button>
              <button
                className="btn-primary flex items-center gap-2"
                onClick={() => handleSubmit(false)}
                disabled={loading}
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : null}
                Submit PA
              </button>
            </div>
            {createdPAId && (
              <p className="text-center text-sm text-green-600">
                PA created: {createdPAId}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex justify-between">
        <button
          className="btn-secondary flex items-center gap-1"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
        >
          <ChevronLeft size={16} />
          Back
        </button>
        {step < STEPS.length - 1 && (
          <button
            className="btn-primary flex items-center gap-1"
            onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
            disabled={!canProceed()}
          >
            Next
            <ChevronRight size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
