const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011";

interface ApiError {
  message: string;
  status: number;
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error: ApiError = {
      message: `API error: ${res.statusText}`,
      status: res.status,
    };
    throw error;
  }

  return res.json() as Promise<T>;
}

// --- Types ---

export interface StatusHistoryEvent {
  from: string | null;
  to: string;
  actor: string;
  detail: string;
  timestamp: string;
}

export interface PARequest {
  id: string;
  patientId: string;
  cptCode: string;
  icdCodes: string[];
  payerName: string;
  payerId: string;
  practiceId: string;
  practiceName: string;
  status: string;
  approvalProbability: number;
  clinicalExtract: Record<string, unknown> | null;
  justificationDraft: string | null;
  justificationFinal: string | null;
  probabilityFactors: Record<string, unknown>[] | null;
  denialReasonCode: string | null;
  denialReasonText: string | null;
  createdAt: string;
  updatedAt: string;
  submittedAt: string | null;
  decisionAt: string | null;
  outcome: string | null;
  covermymedsPaId: string | null;
  estimatedDecisionDate: string | null;
  statusHistory: StatusHistoryEvent[];
}

export interface TimelineEvent {
  timestamp: string;
  event: string;
  detail: string;
}

export interface DashboardStats {
  totalPAs: number;
  approvalRate: number;
  avgDays: number;
  revenueRecovered: number;
  byStatus: {
    approved: number;
    denied: number;
    pending: number;
    appealed: number;
  };
  denialRatesByPayer: {
    payer: string;
    denialRate: number;
    cptBreakdown: { cpt: string; denialRate: number }[];
  }[];
}

export interface Payer {
  id: string;
  name: string;
}

export interface Practice {
  id: string;
  name: string;
}

export interface AnalyzeResponse {
  clinical_extract: Record<string, unknown>;
  processing_time_ms: number;
}

export interface QualityScore {
  completeness: number;
  payer_specificity: number;
  clinical_accuracy: number;
  overall: number;
  suggestions: string[];
}

export interface ProbabilityResult {
  probability: number;
  confidence: "low" | "medium" | "high";
  factors: { name: string; impact: number; description: string; met: boolean }[];
  recommendation: string;
}

export interface DraftResponse {
  justification: string;
  gaps: string[];
  quality_score: QualityScore;
  probability: ProbabilityResult;
  processing_time_ms: number;
}

export interface CreatePAData {
  practice_id: string;
  payer_id: string;
  patient_id: string;
  cpt_code: string;
  icd10_codes: string[];
}

// --- Mappers (snake_case API → camelCase frontend) ---

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapPA(raw: any): PARequest {
  return {
    id: raw.id,
    patientId: raw.patient_id,
    cptCode: raw.cpt_code,
    icdCodes: raw.icd10_codes || [],
    payerName: raw.payer_name || "",
    payerId: raw.payer_id,
    practiceId: raw.practice_id,
    practiceName: raw.practice_name || "",
    status: raw.status,
    approvalProbability: parseFloat(raw.approval_probability) || 0,
    clinicalExtract: raw.clinical_extract,
    justificationDraft: raw.justification_draft,
    justificationFinal: raw.justification_final,
    probabilityFactors: raw.probability_factors,
    denialReasonCode: raw.denial_reason_code,
    denialReasonText: raw.denial_reason_text,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    submittedAt: raw.submitted_at,
    decisionAt: raw.decision_at,
    outcome: raw.outcome,
    covermymedsPaId: raw.covermymeds_pa_id || null,
    estimatedDecisionDate: raw.estimated_decision_date || null,
    statusHistory: raw.status_history || [],
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapDashboardStats(raw: any): DashboardStats {
  const statusMap: Record<string, number> = {};
  for (const row of raw.status_breakdown || []) {
    statusMap[row.status] = parseInt(row.count);
  }
  return {
    totalPAs: raw.total_this_month || 0,
    approvalRate: parseFloat(raw.approval_rate) || 0,
    avgDays: parseFloat(raw.avg_processing_days) || 0,
    revenueRecovered: raw.revenue_recovered || 0,
    byStatus: {
      approved: statusMap["approved"] || 0,
      denied: statusMap["denied"] || 0,
      pending: (statusMap["submitted"] || 0) + (statusMap["draft"] || 0),
      appealed: statusMap["appealed"] || 0,
    },
    denialRatesByPayer: (raw.by_payer || []).map(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (p: any) => ({
        payer: p.payer_name,
        denialRate: p.total > 0 ? (parseInt(p.denied) / parseInt(p.total)) * 100 : 0,
        cptBreakdown: [],
      })
    ),
  };
}

// --- API Functions ---

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const raw = await request<unknown>("/api/dashboard/stats");
  return mapDashboardStats(raw);
}

export async function fetchPAList(): Promise<PARequest[]> {
  const raw = await request<unknown[]>("/api/pa/list");
  return raw.map(mapPA);
}

export async function fetchPA(id: string): Promise<PARequest> {
  const raw = await request<unknown>(`/api/pa/${encodeURIComponent(id)}`);
  return mapPA(raw);
}

export async function createPA(data: CreatePAData): Promise<PARequest> {
  const raw = await request<unknown>("/api/pa/create", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapPA(raw);
}

export async function analyzePA(data: {
  clinical_text: string;
  pa_id?: string;
}): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/api/pa/analyze", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function draftPA(data: {
  clinical_extract: Record<string, unknown>;
  cpt_code: string;
  payer_id: string;
  pa_id?: string;
}): Promise<DraftResponse> {
  return request<DraftResponse>("/api/pa/draft", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface SubmitPAResponse {
  pa: PARequest;
  submission: {
    paId: string;
    estimatedDecisionDate: string;
  };
}

export async function submitPA(
  id: string,
  justification_final?: string,
  actor?: string
): Promise<SubmitPAResponse> {
  const raw = await request<{ pa: unknown; submission: { paId: string; estimatedDecisionDate: string } }>(
    `/api/pa/${encodeURIComponent(id)}/submit`,
    {
      method: "POST",
      body: JSON.stringify({ justification_final, actor }),
    }
  );
  return {
    pa: mapPA(raw.pa),
    submission: raw.submission,
  };
}

export interface PAStatusResponse {
  id: string;
  status: string;
  covermymeds_pa_id: string | null;
  submitted_at: string | null;
  estimated_decision_date: string | null;
  decision_at: string | null;
  outcome: string | null;
  denial_reason_code: string | null;
  denial_reason_text: string | null;
  days_pending: number | null;
  status_history: StatusHistoryEvent[];
}

export async function fetchPAStatus(id: string): Promise<PAStatusResponse> {
  return request<PAStatusResponse>(`/api/pa/${encodeURIComponent(id)}/status`);
}

export interface RefreshPAResponse {
  pa: PARequest;
  changed: boolean;
  previousStatus?: string;
  newStatus?: string;
  message?: string;
}

export async function refreshPA(id: string): Promise<RefreshPAResponse> {
  const raw = await request<{ pa: unknown; changed: boolean; previousStatus?: string; newStatus?: string; message?: string }>(
    `/api/pa/${encodeURIComponent(id)}/refresh`,
    { method: "POST" }
  );
  return {
    ...raw,
    pa: mapPA(raw.pa),
  };
}

export async function generateJustification(paId: string): Promise<DraftResponse> {
  return request<DraftResponse>(`/api/pa/${encodeURIComponent(paId)}/generate-justification`, {
    method: "POST",
  });
}

export async function saveJustification(
  paId: string,
  justificationFinal: string
): Promise<{ pa: unknown; edit_percentage: number }> {
  return request<{ pa: unknown; edit_percentage: number }>(
    `/api/pa/${encodeURIComponent(paId)}/save-justification`,
    {
      method: "POST",
      body: JSON.stringify({ justification_final: justificationFinal }),
    }
  );
}

export async function scorePA(paId: string): Promise<ProbabilityResult> {
  return request<ProbabilityResult>(
    `/api/pa/${encodeURIComponent(paId)}/score`,
    { method: "POST" }
  );
}

export async function fetchPayers(): Promise<Payer[]> {
  return request<Payer[]>("/api/payers");
}

export async function fetchPractices(): Promise<Practice[]> {
  return request<Practice[]>("/api/practices");
}

// --- Payer Requirements ---

export interface PayerRequirementCriterion {
  id: string;
  category: string;
  description: string;
  required: boolean;
}

export interface PayerRequirement {
  payer_id: string;
  payer_name: string;
  cpt_code: string;
  description: string;
  requires_pa: boolean;
  criteria: PayerRequirementCriterion[];
  supporting_docs_required: string[];
  clinical_guidelines: string[];
  avg_approval_days: number;
  denial_rate_estimate: number;
  common_denial_reasons: string[];
  tips: string;
  source?: string;
}

export interface GapCheckResult {
  payer_id: string;
  cpt_code: string;
  requirements: PayerRequirement;
  gaps: {
    met: (PayerRequirementCriterion & { status: string })[];
    missing: (PayerRequirementCriterion & { status: string })[];
    uncertain: (PayerRequirementCriterion & { status: string })[];
  };
  summary: {
    total: number;
    met: number;
    missing: number;
    uncertain: number;
  };
}

export async function fetchPayerRequirements(params?: {
  payer_id?: string;
  cpt_code?: string;
  search?: string;
}): Promise<PayerRequirement[]> {
  const query = new URLSearchParams();
  if (params?.payer_id) query.set("payer_id", params.payer_id);
  if (params?.cpt_code) query.set("cpt_code", params.cpt_code);
  if (params?.search) query.set("search", params.search);
  const qs = query.toString();
  return request<PayerRequirement[]>(`/api/payers/requirements${qs ? `?${qs}` : ""}`);
}

export async function fetchPayerRequirement(
  payerId: string,
  cptCode: string
): Promise<PayerRequirement> {
  return request<PayerRequirement>(
    `/api/payers/${encodeURIComponent(payerId)}/requirements/${encodeURIComponent(cptCode)}`
  );
}

export async function checkGaps(
  payerId: string,
  cptCode: string,
  clinicalExtract: Record<string, unknown>
): Promise<GapCheckResult> {
  return request<GapCheckResult>(
    `/api/payers/${encodeURIComponent(payerId)}/requirements/${encodeURIComponent(cptCode)}/check-gaps`,
    {
      method: "POST",
      body: JSON.stringify({ clinical_extract: clinicalExtract }),
    }
  );
}

// --- Appeal Types ---

export interface CarcStrategy {
  code: string;
  name: string;
  strategy: string;
  required_evidence: string[];
  success_rate_estimate: number;
  typical_resolution_days: number;
  escalation_path: string;
}

export interface Appeal {
  id: string;
  pa_request_id: string;
  appeal_draft: string | null;
  appeal_final: string | null;
  appeal_type: string;
  deadline_date: string | null;
  escalation_type: string;
  denial_reason_code: string | null;
  carc_strategy: CarcStrategy | null;
  submitted_at: string | null;
  outcome: string | null;
  outcome_date: string | null;
  days_remaining: number | null;
  created_at: string;
}

export interface GenerateAppealResponse {
  appeal: Appeal;
  appeal_draft: string;
  appeal_type: string;
  escalation_recommended: boolean;
  deadline_date: string;
  carc_strategy: CarcStrategy | null;
  processing_time_ms: number;
}

export interface AppealStats {
  by_carc_code: {
    carc_code: string;
    total_appeals: number;
    won: number;
    lost: number;
    pending: number;
    win_rate: string | null;
    avg_days_to_resolve: string | null;
  }[];
  by_payer: {
    payer_name: string;
    total_appeals: number;
    won: number;
    lost: number;
    pending: number;
    win_rate: string | null;
    avg_days_to_overturn: string | null;
  }[];
  urgent_appeals: {
    id: string;
    pa_request_id: string;
    deadline_date: string;
    escalation_type: string;
    denial_reason_code: string;
    cpt_code: string;
    patient_id: string;
    payer_name: string;
    days_remaining: number;
  }[];
  all_pending_appeals: {
    id: string;
    pa_request_id: string;
    deadline_date: string;
    days_remaining: number;
    payer_name: string;
    cpt_code: string;
  }[];
  most_winnable: {
    code: string;
    name: string;
    estimated_win_rate: number;
    actual_win_rate: number | null;
    total_appeals: number;
    typical_resolution_days: number;
  }[];
}

// --- Appeal API Functions ---

export async function generateAppeal(paId: string): Promise<GenerateAppealResponse> {
  return request<GenerateAppealResponse>(
    `/api/pa/${encodeURIComponent(paId)}/generate-appeal`,
    { method: "POST" }
  );
}

export async function submitAppeal(
  paId: string,
  appealFinal?: string,
  actor?: string
): Promise<{ success: boolean; appeal_id: string; covermymeds_pa_id: string }> {
  return request<{ success: boolean; appeal_id: string; covermymeds_pa_id: string }>(
    `/api/pa/${encodeURIComponent(paId)}/submit-appeal`,
    {
      method: "POST",
      body: JSON.stringify({ appeal_final: appealFinal, actor }),
    }
  );
}

export async function fetchAppeals(paId: string): Promise<Appeal[]> {
  return request<Appeal[]>(`/api/pa/${encodeURIComponent(paId)}/appeals`);
}

export async function fetchAppealStats(): Promise<AppealStats> {
  return request<AppealStats>("/api/dashboard/appeal-stats");
}

// --- Activity Feed ---

export interface ActivityEvent {
  id: string;
  pa_id: string;
  patient_id: string;
  payer_name: string;
  cpt_code: string;
  event: string;
  detail: string;
  timestamp: string;
}

export async function fetchActivityFeed(): Promise<ActivityEvent[]> {
  return request<ActivityEvent[]>("/api/dashboard/activity-feed");
}

export async function fetchConfig(): Promise<{ demoMode: boolean }> {
  return request<{ demoMode: boolean }>("/api/config");
}
