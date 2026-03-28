-- AuthAgent MVP Schema
-- PHI: treat as sensitive

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE practices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  npi TEXT,
  specialty TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE payers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  payer_id TEXT,
  fhir_endpoint TEXT,
  covermymeds_id TEXT
);

CREATE TABLE payer_requirements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payer_id UUID REFERENCES payers(id),
  cpt_code TEXT NOT NULL,
  requires_pa BOOLEAN DEFAULT true,
  criteria JSONB,
  supporting_docs TEXT[],
  avg_approval_days DECIMAL,
  denial_rate_estimate DECIMAL,
  last_updated TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pa_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  practice_id UUID REFERENCES practices(id),
  payer_id UUID REFERENCES payers(id),
  patient_id TEXT, -- PHI: treat as sensitive
  cpt_code TEXT NOT NULL,
  icd10_codes TEXT[],
  status TEXT DEFAULT 'draft',
  clinical_extract JSONB, -- PHI: treat as sensitive
  justification_draft TEXT,
  justification_final TEXT,
  approval_probability DECIMAL,
  probability_factors JSONB,
  covermymeds_pa_id TEXT,
  submitted_at TIMESTAMPTZ,
  decision_at TIMESTAMPTZ,
  outcome TEXT,
  denial_reason_code TEXT,
  denial_reason_text TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pa_appeals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_request_id UUID REFERENCES pa_requests(id),
  appeal_draft TEXT,
  appeal_final TEXT,
  appeal_type TEXT,
  submitted_at TIMESTAMPTZ,
  outcome TEXT,
  outcome_date TIMESTAMPTZ
);

CREATE TABLE uploaded_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_request_id UUID REFERENCES pa_requests(id),
  doc_type TEXT,
  filename TEXT,
  filepath TEXT,
  extracted_text TEXT, -- PHI: treat as sensitive
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_pa_requests_status ON pa_requests(status);
CREATE INDEX idx_pa_requests_practice ON pa_requests(practice_id);
CREATE INDEX idx_pa_requests_payer ON pa_requests(payer_id);
CREATE INDEX idx_payer_requirements_lookup ON payer_requirements(payer_id, cpt_code);
