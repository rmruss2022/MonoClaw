/**
 * Payer Requirements Service
 *
 * Business logic for looking up payer requirements.
 * Priority: 1) Redis cache, 2) CoverMyMeds API, 3) Local JSON DB, 4) Postgres
 */

const path = require('path');
const { createClient } = require('redis');
const db = require('../db');
const { CoverMyMedsClient } = require('../fhir/coverMyMeds');

const CACHE_TTL = 900; // 15 minutes in seconds
const CACHE_PREFIX = 'payer_req:';

let redisClient = null;
let redisReady = false;

async function getRedis() {
  if (redisClient && redisReady) return redisClient;

  const url = process.env.REDIS_URL || 'redis://localhost:6379';
  try {
    redisClient = createClient({ url });
    redisClient.on('error', (err) => {
      console.error('Redis error:', err.message);
      redisReady = false;
    });
    redisClient.on('ready', () => {
      redisReady = true;
    });
    await redisClient.connect();
    redisReady = true;
    return redisClient;
  } catch (err) {
    console.warn('Redis unavailable, falling back to no cache:', err.message);
    redisReady = false;
    return null;
  }
}

// Load local requirements JSON
let localRequirements = null;
function getLocalRequirements() {
  if (localRequirements) return localRequirements;
  try {
    // From packages/api/src/services/ → project root src/data/
    localRequirements = require('../../../../src/data/payerRequirements.json');
    return localRequirements;
  } catch (err) {
    // Try alternate path (when cwd is packages/api)
    try {
      localRequirements = require('../../src/data/payerRequirements.json');
      return localRequirements;
    } catch (err2) {
      console.warn('Local payerRequirements.json not found');
      return [];
    }
  }
}

const coverMyMeds = new CoverMyMedsClient();

/**
 * Get requirements for a specific payer + CPT code.
 * Checks: Redis cache → CoverMyMeds API → Local JSON → Postgres
 */
async function getRequirements(payerId, cptCode) {
  const cacheKey = `${CACHE_PREFIX}${payerId}:${cptCode}`;

  // 1. Check Redis cache
  try {
    const redis = await getRedis();
    if (redis) {
      const cached = await redis.get(cacheKey);
      if (cached) {
        return { ...JSON.parse(cached), source: 'cache' };
      }
    }
  } catch (err) {
    // Redis miss or error, continue
  }

  // 2. Try CoverMyMeds API (if not demo mode)
  let result = null;
  if (process.env.DEMO_MODE !== 'true') {
    try {
      const cmmResult = await coverMyMeds.getPayerRequirements(payerId, cptCode);
      if (cmmResult && cmmResult.criteria && cmmResult.criteria.length > 0) {
        result = { ...cmmResult, source: 'covermymeds' };
      }
    } catch (err) {
      // CoverMyMeds unavailable, continue to fallbacks
    }
  }

  // 3. Fall back to local JSON
  if (!result) {
    const local = getLocalRequirements();
    const match = local.find(
      (r) => r.payer_id === payerId && r.cpt_code === cptCode
    );
    if (match) {
      result = { ...match, source: 'local_db' };
    }
  }

  // 4. Fall back to Postgres
  if (!result) {
    try {
      const { rows } = await db.query(
        `SELECT pr.*, p.name as payer_name
         FROM payer_requirements pr
         JOIN payers p ON p.id = pr.payer_id
         WHERE p.payer_id = $1 AND pr.cpt_code = $2`,
        [payerId, cptCode]
      );
      if (rows.length > 0) {
        const row = rows[0];
        result = {
          payer_id: payerId,
          payer_name: row.payer_name,
          cpt_code: row.cpt_code,
          requires_pa: row.requires_pa,
          criteria: row.criteria || [],
          supporting_docs_required: row.supporting_docs || [],
          avg_approval_days: parseFloat(row.avg_approval_days) || 0,
          denial_rate_estimate: parseFloat(row.denial_rate_estimate) || 0,
          source: 'postgres',
        };
      }
    } catch (err) {
      console.error('Postgres query failed:', err.message);
    }
  }

  // Cache the result if found
  if (result) {
    try {
      const redis = await getRedis();
      if (redis) {
        await redis.set(cacheKey, JSON.stringify(result), { EX: CACHE_TTL });
      }
    } catch (err) {
      // Cache write failed, not critical
    }
  }

  return result || null;
}

/**
 * Get all requirements for a payer (all CPT codes).
 */
async function getPayerAllRequirements(payerId) {
  const local = getLocalRequirements();
  const matches = local.filter((r) => r.payer_id === payerId);

  if (matches.length > 0) {
    return matches;
  }

  // Fall back to Postgres
  try {
    const { rows } = await db.query(
      `SELECT pr.*, p.name as payer_name
       FROM payer_requirements pr
       JOIN payers p ON p.id = pr.payer_id
       WHERE p.payer_id = $1
       ORDER BY pr.cpt_code`,
      [payerId]
    );
    return rows.map((row) => ({
      payer_id: payerId,
      payer_name: row.payer_name,
      cpt_code: row.cpt_code,
      requires_pa: row.requires_pa,
      criteria: row.criteria || [],
      supporting_docs_required: row.supporting_docs || [],
      avg_approval_days: parseFloat(row.avg_approval_days) || 0,
      denial_rate_estimate: parseFloat(row.denial_rate_estimate) || 0,
      source: 'postgres',
    }));
  } catch (err) {
    console.error('Error fetching payer requirements:', err.message);
    return [];
  }
}

/**
 * Get all requirements (all payers, all CPT codes).
 */
async function getAllRequirements() {
  const local = getLocalRequirements();
  if (local.length > 0) {
    return local;
  }

  try {
    const { rows } = await db.query(
      `SELECT pr.*, p.name as payer_name, p.payer_id as payer_key
       FROM payer_requirements pr
       JOIN payers p ON p.id = pr.payer_id
       ORDER BY p.name, pr.cpt_code`
    );
    return rows.map((row) => ({
      payer_id: row.payer_key,
      payer_name: row.payer_name,
      cpt_code: row.cpt_code,
      requires_pa: row.requires_pa,
      criteria: row.criteria || [],
      supporting_docs_required: row.supporting_docs || [],
      avg_approval_days: parseFloat(row.avg_approval_days) || 0,
      denial_rate_estimate: parseFloat(row.denial_rate_estimate) || 0,
      source: 'postgres',
    }));
  } catch (err) {
    console.error('Error fetching all requirements:', err.message);
    return [];
  }
}

/**
 * Check gaps: given clinical extract + requirements, determine what's met vs missing.
 */
function checkGaps(clinicalExtract, requirements) {
  if (!clinicalExtract || !requirements || !requirements.criteria) {
    return { met: [], missing: [], uncertain: [] };
  }

  const extract = clinicalExtract;
  const extractText = JSON.stringify(extract).toLowerCase();

  const met = [];
  const missing = [];
  const uncertain = [];

  for (const criterion of requirements.criteria) {
    const desc = criterion.description.toLowerCase();
    const category = criterion.category;

    let status = 'missing';

    if (category === 'conservative_treatment') {
      if (extractText.includes('physical therapy') || extractText.includes(' pt ') ||
          extractText.includes('conservative') || extractText.includes('rehabilitation')) {
        status = 'met';
      }
    } else if (category === 'medication') {
      if (extractText.includes('nsaid') || extractText.includes('medication') ||
          extractText.includes('analgesic') || extractText.includes('failed') ||
          extractText.includes('ibuprofen') || extractText.includes('naproxen') ||
          extractText.includes('gabapentin') || extractText.includes('prescribed')) {
        status = 'met';
      }
    } else if (category === 'clinical_findings') {
      if (extractText.includes('symptom') || extractText.includes('finding') ||
          extractText.includes('radiculopathy') || extractText.includes('pain') ||
          extractText.includes('deficit') || extractText.includes('positive')) {
        status = 'met';
      }
    } else if (category === 'diagnostic') {
      if (extractText.includes('imaging') || extractText.includes('x-ray') ||
          extractText.includes('mri') || extractText.includes('ct ') ||
          extractText.includes('lab') || extractText.includes('test result')) {
        status = 'met';
      }
    } else if (category === 'documentation') {
      const hasNotes = extract.provider_assessment || extract.physical_exam;
      if (hasNotes) status = 'met';
      else status = 'uncertain';
    } else if (category === 'functional_assessment') {
      if (extractText.includes('score') || extractText.includes('scale') ||
          extractText.includes('functional') || extractText.includes('disability') ||
          extractText.includes('oxford') || extractText.includes('vas ')) {
        status = 'met';
      }
    } else if (category === 'specialist_referral') {
      if (extractText.includes('referral') || extractText.includes('specialist') ||
          extractText.includes('consult')) {
        status = 'met';
      }
    } else if (category === 'behavioral' || category === 'psychological') {
      if (extractText.includes('psycholog') || extractText.includes('behavioral') ||
          extractText.includes('mental health') || extractText.includes('screening')) {
        status = 'met';
      }
    } else if (category === 'prior_treatment') {
      if (extract.prior_treatments && extract.prior_treatments.length > 0) {
        status = 'met';
      }
    } else if (category === 'medical_history') {
      if (extract.secondary_diagnoses || extract.symptoms) {
        status = 'met';
      } else {
        status = 'uncertain';
      }
    } else {
      // Unknown category — try keyword matching
      const keywords = desc.split(/\s+/).filter((w) => w.length > 4);
      const matchCount = keywords.filter((w) => extractText.includes(w)).length;
      if (matchCount >= keywords.length * 0.4) status = 'met';
      else if (matchCount > 0) status = 'uncertain';
    }

    const item = { ...criterion, status };
    if (status === 'met') met.push(item);
    else if (status === 'uncertain') uncertain.push(item);
    else missing.push(item);
  }

  return { met, missing, uncertain };
}

module.exports = {
  getRequirements,
  getPayerAllRequirements,
  getAllRequirements,
  checkGaps,
  getRedis,
};
