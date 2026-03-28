/**
 * CoverMyMeds API client with sandbox mode.
 *
 * Modes:
 *   - demo: Returns mock responses with simulated delays (DEMO_MODE=true or no API key)
 *   - sandbox: Hits CoverMyMeds sandbox API (COVERMYMEDS_ENV=sandbox)
 *   - production: Hits CoverMyMeds production API (COVERMYMEDS_ENV=production)
 *
 * CoverMyMeds developer API: https://developer.covermymeds.com
 */

const ENDPOINTS = {
  sandbox: 'https://api.sandbox.covermymeds.com/v1',
  production: 'https://api.covermymeds.com/v1',
};

// In-memory store for demo mode PA simulations
const demoPAStore = new Map();

class CoverMyMedsClient {
  constructor(apiKey, options = {}) {
    this.apiKey = apiKey || process.env.COVERMYMEDS_API_KEY || 'demo';
    this.env = options.env || process.env.COVERMYMEDS_ENV || 'demo';
    this.isDemoMode = process.env.DEMO_MODE === 'true' || this.apiKey === 'demo' || this.env === 'demo';
    this.baseUrl = ENDPOINTS[this.env] || ENDPOINTS.sandbox;
    this.timeout = options.timeout || 10000;
  }

  /**
   * Internal fetch wrapper with auth headers and timeout.
   */
  async _request(method, path, body = null) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const options = {
        method,
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        signal: controller.signal,
      };

      if (body) {
        options.body = JSON.stringify(body);
      }

      const response = await fetch(`${this.baseUrl}${path}`, options);

      if (!response.ok) {
        const errorBody = await response.text().catch(() => '');
        throw new Error(`CoverMyMeds API error ${response.status}: ${errorBody}`);
      }

      return await response.json();
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Check if a procedure requires PA for a given payer.
   */
  async checkPARequired(payerId, cptCode) {
    if (this.isDemoMode) {
      const noPA = ['77067'];
      return {
        requires_pa: !noPA.includes(cptCode),
        payer_id: payerId,
        cpt_code: cptCode,
        source: 'demo_mode',
      };
    }

    return this._request('GET', `/pa_determinations?payer_id=${encodeURIComponent(payerId)}&code=${encodeURIComponent(cptCode)}`);
  }

  /**
   * Submit a PA request through CoverMyMeds.
   * @param {Object} paData - PA submission data
   * @returns {{ paId: string, status: string, estimatedDecisionDate: string }}
   */
  async submitPA(paData) {
    if (this.isDemoMode) {
      const paId = `CMM-DEMO-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      const submittedAt = new Date().toISOString();
      // Simulate 2-minute decision in demo, 3-day in sandbox
      const decisionDelayMs = 2 * 60 * 1000; // 2 minutes for demo
      const estimatedDecisionDate = new Date(Date.now() + decisionDelayMs).toISOString();

      // 25% denial rate in demo mode
      const willDeny = Math.random() < 0.25;

      // Store simulation state
      demoPAStore.set(paId, {
        paId,
        status: 'pending_decision',
        submittedAt,
        estimatedDecisionDate,
        willDeny,
        decisionTime: Date.now() + decisionDelayMs,
        denialReason: willDeny ? {
          code: ['CO-50', 'CO-4', 'CO-197', 'CO-96'][Math.floor(Math.random() * 4)],
          text: [
            'Not medically necessary per payer clinical policy',
            'Procedure code inconsistent with diagnosis',
            'Precertification/authorization not obtained in time',
            'Non-covered service for this plan',
          ][Math.floor(Math.random() * 4)],
        } : null,
        cptCode: paData.cpt_code,
        payerId: paData.payer_id,
      });

      return {
        paId,
        status: 'pending_decision',
        submittedAt,
        estimatedDecisionDate,
        source: 'demo_mode',
      };
    }

    const result = await this._request('POST', '/pa_requests', {
      pa_request: {
        payer_id: paData.payer_id,
        patient: paData.patient,
        prescriber: paData.prescriber,
        prescription: {
          code: paData.cpt_code,
          code_type: 'cpt',
          diagnosis_codes: paData.icd10_codes,
        },
        clinical_info: paData.clinical_info,
      },
    });

    return {
      paId: result.id || result.covermymeds_pa_id,
      status: result.status || 'submitted',
      estimatedDecisionDate: result.estimated_decision_date || new Date(Date.now() + 3 * 86400000).toISOString(),
    };
  }

  /**
   * Get current status of a submitted PA.
   * @param {string} paId - CoverMyMeds PA reference ID
   * @returns {{ paId: string, status: string,决定details }}
   */
  async getStatus(paId) {
    if (this.isDemoMode) {
      const sim = demoPAStore.get(paId);

      if (!sim) {
        // Return a generic pending status for PAs not in our simulation store
        return {
          paId,
          status: 'pending_decision',
          lastUpdated: new Date().toISOString(),
          source: 'demo_mode',
        };
      }

      const now = Date.now();

      // Check if decision time has passed
      if (now >= sim.decisionTime) {
        const finalStatus = sim.willDeny ? 'denied' : 'approved';
        sim.status = finalStatus;

        return {
          paId,
          status: finalStatus,
          lastUpdated: new Date().toISOString(),
          decisionDate: new Date(sim.decisionTime).toISOString(),
          denialReasonCode: sim.willDeny ? sim.denialReason.code : null,
          denialReasonText: sim.willDeny ? sim.denialReason.text : null,
          source: 'demo_mode',
        };
      }

      // Still pending — return progress indication
      const elapsed = now - new Date(sim.submittedAt).getTime();
      const total = sim.decisionTime - new Date(sim.submittedAt).getTime();
      const progress = Math.min(95, Math.round((elapsed / total) * 100));

      return {
        paId,
        status: 'pending_decision',
        lastUpdated: new Date().toISOString(),
        progress,
        estimatedDecisionDate: sim.estimatedDecisionDate,
        source: 'demo_mode',
      };
    }

    const result = await this._request('GET', `/pa_requests/${encodeURIComponent(paId)}`);

    return {
      paId,
      status: result.status,
      lastUpdated: result.updated_at || new Date().toISOString(),
      decisionDate: result.decision_date || null,
      denialReasonCode: result.denial_reason_code || null,
      denialReasonText: result.denial_reason_text || null,
    };
  }

  /**
   * Get payer requirements for a specific CPT code.
   */
  async getPayerRequirements(payerId, cptCode) {
    if (this.isDemoMode) {
      return {
        payer_id: payerId,
        cpt_code: cptCode,
        requires_pa: true,
        fields_required: ['diagnosis', 'clinical_notes', 'prior_treatments', 'medications'],
        documents_required: ['office_notes', 'lab_results'],
        questions: [
          { id: 'q1', text: 'Has the patient tried conservative treatment?', type: 'boolean' },
          { id: 'q2', text: 'Duration of symptoms (weeks)?', type: 'number' },
          { id: 'q3', text: 'Prior imaging results?', type: 'text' },
        ],
        source: 'demo_mode',
      };
    }

    return this._request('GET', `/payer_forms?payer_id=${encodeURIComponent(payerId)}&code=${encodeURIComponent(cptCode)}&code_type=cpt`);
  }

  /**
   * Search for payers by name.
   */
  async searchPayers(query) {
    if (this.isDemoMode) {
      const demoPayersAll = [
        { id: 'united_healthcare', name: 'United Healthcare', covermymeds_id: 'UHC001' },
        { id: 'aetna', name: 'Aetna', covermymeds_id: 'AETNA001' },
        { id: 'cigna', name: 'Cigna', covermymeds_id: 'CIGNA001' },
        { id: 'humana', name: 'Humana', covermymeds_id: 'HUMANA001' },
        { id: 'bcbs', name: 'BlueCross BlueShield', covermymeds_id: 'BCBS001' },
      ];
      const q = query.toLowerCase();
      return demoPayersAll.filter((p) => p.name.toLowerCase().includes(q));
    }

    return this._request('GET', `/payers?search=${encodeURIComponent(query)}`);
  }
}

// Singleton for convenience
let _client = null;
function getClient() {
  if (!_client) {
    _client = new CoverMyMedsClient();
  }
  return _client;
}

module.exports = { CoverMyMedsClient, getClient, demoPAStore };
