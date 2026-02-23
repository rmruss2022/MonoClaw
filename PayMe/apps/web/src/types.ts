export type Match = {
  settlement_id: string;
  title: string;
  score: number;
  summary_text?: string | null;
  claim_url?: string | null;
  website_url?: string | null;
  payout_min_cents?: number | null;
  payout_max_cents?: number | null;
  deadline?: string | null;
  states?: string[];
  claim_status?: "submitted" | "paid_out" | "not_paid_out" | null;
  claim_submitted_at?: string | null;
  claim_outcome_at?: string | null;
  pinned: boolean;
  reasons_json: {
    matched_features?: string[];
    confidence_breakdown?: Record<string, number>;
  };
};

export type OngoingClaim = {
  settlement_id: string;
  title: string;
  claim_url?: string | null;
  claim_status: "submitted" | "paid_out" | "not_paid_out";
  claim_submitted_at?: string | null;
  claim_outcome_at?: string | null;
  score?: number | null;
};

export type ClaimHistoryItem = {
  settlement_id: string;
  title: string;
  claim_url?: string | null;
  claim_status: "paid_out" | "not_paid_out";
  claim_submitted_at?: string | null;
  claim_outcome_at?: string | null;
  amount_paid_cents?: number | null;
};

export type SettlementDetail = {
  id: string;
  title: string;
  summary_text: string;
  eligibility_text: string;
  status: string;
  claim_url: string;
  website_url?: string;
  payout_min_cents?: number | null;
  payout_max_cents?: number | null;
  deadline?: string | null;
  states?: string[];
  claim_status?: "submitted" | "paid_out" | "not_paid_out" | null;
  claim_submitted_at?: string | null;
  claim_outcome_at?: string | null;
};

export type AuthUser = {
  id: string;
  username: string;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  state?: string | null;
  gmail_synced_at?: string | null;
  plaid_synced_at?: string | null;
  gmail_oauth_connected?: boolean;
  plaid_linked?: boolean;
  plaid_institution_name?: string | null;
  plaid_balance_available_cents?: number | null;
  plaid_balance_current_cents?: number | null;
  role?: string;
};

export type AutofillStep = {
  id: string;
  step_name: string;
  status: string;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
};

export type AutofillJob = {
  id: string;
  user_id: string;
  settlement_id: string;
  status: string;
  attempt_count: number;
  claim_url?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
  steps: AutofillStep[];
  artifact_keys: string[];
};

export type MlSample = {
  user_id: string;
  settlement_id: string;
  run_id: string;
  rules_confidence: number;
  similarity: number;
  payout: number;
  urgency: number;
  ease: number;
  label: number | null;
  outcome: string;
  export_version: number;
  created_at: string;
  updated_at: string;
};

export type AttorneySession = {
  attorney_id: string;
  api_key: string;
  name: string;
  email: string;
};

export type GatewayClaimant = {
  user_id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  submitted_at: string;
};

export type PayoutBatch = {
  batch_id: string;
  status: string;
  total_transfers: number;
  total_amount_cents: number;
  successful_transfers?: number;
  failed_transfers?: number;
};

export type PayoutQueueItem = {
  user_id: string;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  settlement_id: string;
  settlement_title: string;
  settlement_payout_min_cents?: number | null;
  submitted_at: string;
  approval_id?: string | null;
  approval_status: "pending" | "approved" | "rejected" | "paid" | "failed";
  approved_amount_cents?: number | null;
};

export type PayoutHistoryItem = {
  transfer_id: string;
  batch_id: string;
  user_id: string;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  settlement_id: string;
  settlement_title: string;
  amount_cents: number;
  status: string;
  provider_transfer_id?: string | null;
  failure_reason?: string | null;
  initiated_at?: string | null;
  completed_at?: string | null;
};

export type AdminOverview = Record<string, number>;

export type AdminUser = {
  id: string;
  username: string;
  email: string;
  state: string | null;
  match_count: number;
};

export type AdminSettlement = {
  id: string;
  title: string;
  status: string;
  feature_index_count: number;
};

export type AdminEvent = {
  id: string;
  type: string;
  user_id: string | null;
};

export type UserStats = {
  user_id: string;
  total_match_results: number;
  latest_run_id: string | null;
  latest_run_result_count: number;
  average_score: number;
  gmail_messages: number;
  plaid_transactions: number;
};

export type SettlementQuestion = {
  id: string;
  settlement_id: string;
  question_text: string;
  question_type: "text" | "yes_no" | "date" | "amount" | "select";
  options_json?: string[] | null;
  order_index: number;
  required: boolean;
};

export type ClaimEvidence = {
  gmail: Array<{ id: string; subject: string; from_domain: string; internal_date: string; snippet: string }>;
  plaid: Array<{ id: string; merchant_name: string; amount_cents: number; posted_at: string; category: string }>;
};

export type ClaimSubmitResult = {
  auto_approved: boolean;
  auto_match_score: number;
  payout_triggered: boolean;
  amount_cents?: number | null;
};
