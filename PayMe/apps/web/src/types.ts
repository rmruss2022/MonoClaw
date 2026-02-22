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
