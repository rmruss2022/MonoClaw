/**
 * Rule-based approval probability scoring (Loop 4).
 * Uses CMS-derived base denial rates and a risk factor rules engine
 * to predict PA approval probability.
 *
 * MVP implementation — will be replaced with ML model in Loop 10.
 */

const path = require('path');
const baseDenialRates = require(path.join(__dirname, '../../../../src/data/baseDenialRates.json'));
const riskFactorsConfig = require(path.join(__dirname, '../../../../src/data/riskFactors.json'));

/**
 * Get the base approval rate for a CPT code and payer combination.
 * Falls back to commercial average, then category average, then default.
 */
function getBaseApprovalRate(cptCode, payerName) {
  const cptData = baseDenialRates.rates[cptCode];
  if (!cptData) {
    return { rate: 0.70, source: 'default' };
  }

  // Try payer-specific rate first
  if (payerName && cptData.payers[payerName]) {
    const denialRate = cptData.payers[payerName];
    return { rate: 1 - denialRate, source: `${payerName} data` };
  }

  // Fall back to commercial average
  return { rate: 1 - cptData.commercial_avg, source: 'commercial average' };
}

/**
 * Check if a clinical extract contains evidence matching detection criteria.
 */
function detectEvidence(clinicalFacts, detectionFields, detectionKeywords) {
  if (!clinicalFacts) return false;

  const fieldsToCheck = detectionFields || [];
  const keywords = (detectionKeywords || []).map(k => k.toLowerCase());

  for (const field of fieldsToCheck) {
    const value = clinicalFacts[field];
    if (!value) continue;

    // Array fields (e.g. prior_treatments, medications)
    if (Array.isArray(value) && value.length > 0) {
      if (keywords.length === 0) return true; // Field exists with data
      const text = value.map(v => typeof v === 'string' ? v : JSON.stringify(v)).join(' ').toLowerCase();
      if (keywords.some(kw => text.includes(kw))) return true;
    }

    // String fields
    if (typeof value === 'string' && value.trim()) {
      if (keywords.length === 0) return true;
      const lower = value.toLowerCase();
      if (keywords.some(kw => lower.includes(kw))) return true;
    }

    // Object fields
    if (typeof value === 'object' && !Array.isArray(value) && value !== null) {
      const text = JSON.stringify(value).toLowerCase();
      if (keywords.length === 0) return true;
      if (keywords.some(kw => text.includes(kw))) return true;
    }

    // Numeric fields (e.g., duration_weeks, bmi)
    if (typeof value === 'number' && value > 0) {
      return true;
    }
  }

  return false;
}

/**
 * Get the procedure category from base denial rates data.
 */
function getCptCategory(cptCode) {
  const cptData = baseDenialRates.rates[cptCode];
  return cptData?.category || 'unknown';
}

/**
 * Evaluate all risk factors against clinical data.
 */
function evaluateRiskFactors(clinicalFacts, payerName, cptCode) {
  const category = getCptCategory(cptCode);
  const factors = [];

  for (const rule of riskFactorsConfig.factors) {
    // Check if this rule applies to this CPT code or category
    const appliesToCpt = rule.applies_to_cpt?.length === 0 || rule.applies_to_cpt?.includes(cptCode);
    const appliesToCategory = !rule.applies_to_categories?.length || rule.applies_to_categories.includes(category);

    if (!appliesToCpt && !appliesToCategory) continue;

    // Special handling for high_scrutiny_payer
    if (rule.id === 'high_scrutiny_payer') {
      if (rule.payer_thresholds && payerName) {
        const scrutinyCodes = rule.payer_thresholds[payerName] || [];
        if (scrutinyCodes.includes(cptCode)) {
          const payerNote = rule.payer_notes?.[payerName] || '';
          factors.push({
            name: rule.name,
            impact: rule.impact_pct,
            description: payerNote || rule.description,
            met: true, // The negative condition IS met (payer IS high-scrutiny)
          });
        }
      }
      continue;
    }

    // Special handling for incomplete_clinical_notes
    if (rule.id === 'incomplete_clinical_notes') {
      const requiredFields = rule.detection_fields || [];
      let presentCount = 0;
      for (const field of requiredFields) {
        const val = clinicalFacts?.[field];
        if (val && (Array.isArray(val) ? val.length > 0 : true)) {
          presentCount++;
        }
      }
      const minRequired = rule.min_required_fields || 3;
      if (presentCount < minRequired) {
        factors.push({
          name: rule.name,
          impact: rule.impact_pct,
          description: `Only ${presentCount} of ${requiredFields.length} key clinical fields documented. ${minRequired}+ needed for strong submission.`,
          met: true,
        });
      }
      continue;
    }

    // Special handling for symptom_duration_adequate
    if (rule.id === 'symptom_duration_adequate') {
      const durationWeeks = clinicalFacts?.duration_weeks || clinicalFacts?.symptom_duration;
      const threshold = rule.duration_thresholds?.[category] || 6;
      if (typeof durationWeeks === 'number' && durationWeeks >= threshold) {
        factors.push({
          name: rule.name,
          impact: rule.impact_pct,
          description: `${durationWeeks} weeks documented (threshold: ${threshold} weeks for ${category}).`,
          met: true,
        });
      } else if (typeof durationWeeks === 'number' && durationWeeks > 0) {
        // Documented but below threshold — slight negative
        factors.push({
          name: `Symptom duration below threshold`,
          impact: -4,
          description: `${durationWeeks} weeks documented, but ${threshold}+ weeks typically required for ${category} procedures.`,
          met: true,
        });
      }
      continue;
    }

    // Standard factor detection
    const evidenceFound = detectEvidence(clinicalFacts, rule.detection_fields, rule.detection_keywords);

    if (rule.direction === 'positive') {
      if (evidenceFound) {
        const payerNote = payerName && rule.payer_notes?.[payerName];
        factors.push({
          name: rule.name,
          impact: rule.impact_pct,
          description: payerNote || rule.description,
          met: true,
        });
      }
      // If positive factor is NOT met, add it as a negative finding
      else if (rule.applies_to_cpt?.includes(cptCode) || (rule.applies_to_categories?.includes(category) && rule.id !== 'peer_reviewed_evidence' && rule.id !== 'specialist_referral_present')) {
        factors.push({
          name: `Missing: ${rule.name.toLowerCase()}`,
          impact: Math.round(-rule.impact_pct * 0.5), // Half penalty for missing positive
          description: `Not found in documentation. ${rule.description}`,
          met: false,
        });
      }
    } else if (rule.direction === 'negative') {
      // "missing_*" factors: negative impact when evidence is ABSENT
      const isMissingType = rule.id.startsWith('missing_');
      if (isMissingType) {
        if (!evidenceFound) {
          const payerNote = payerName && rule.payer_notes?.[payerName];
          factors.push({
            name: rule.name,
            impact: rule.impact_pct,
            description: payerNote || rule.description,
            met: true, // The negative condition (absence) is true
          });
        }
      } else {
        // Standard negative factors (e.g. prior_denial): negative impact when evidence IS present
        if (evidenceFound) {
          const payerNote = payerName && rule.payer_notes?.[payerName];
          factors.push({
            name: rule.name,
            impact: rule.impact_pct,
            description: payerNote || rule.description,
            met: true,
          });
        }
      }
    }
  }

  return factors;
}

/**
 * Determine confidence level based on data quality.
 */
function assessConfidence(clinicalFacts, factors) {
  let dataPoints = 0;

  if (clinicalFacts?.diagnosis || clinicalFacts?.primary_diagnosis) dataPoints++;
  if (clinicalFacts?.symptoms?.length > 0) dataPoints++;
  if (clinicalFacts?.prior_treatments?.length > 0) dataPoints++;
  if (clinicalFacts?.medications?.length > 0) dataPoints++;
  if (clinicalFacts?.duration_weeks) dataPoints++;
  if (clinicalFacts?.severity) dataPoints++;
  if (clinicalFacts?.imaging_results || clinicalFacts?.test_results) dataPoints++;
  if (clinicalFacts?.lab_results) dataPoints++;
  if (clinicalFacts?.clinical_impression) dataPoints++;

  const factorCount = factors.length;

  if (dataPoints >= 6 && factorCount >= 4) return 'high';
  if (dataPoints >= 3 && factorCount >= 2) return 'medium';
  return 'low';
}

/**
 * Generate recommendation based on probability and factors.
 */
function generateRecommendation(probability, factors) {
  const missingFactors = factors.filter(f => !f.met && f.impact < 0);
  const negativeFactors = factors.filter(f => f.met && f.impact < 0);
  const allNegative = [...missingFactors, ...negativeFactors];

  if (probability >= 80) {
    return 'Submit as-is — strong approval likelihood based on complete documentation.';
  }

  if (probability >= 70) {
    if (allNegative.length > 0) {
      const topMissing = allNegative
        .sort((a, b) => a.impact - b.impact)
        .slice(0, 2)
        .map(f => f.name.replace(/^Missing: /, ''));
      return `Good probability. Consider strengthening: ${topMissing.join(', ')}.`;
    }
    return 'Submit as-is — reasonable approval likelihood.';
  }

  if (probability >= 50) {
    const gatherDocs = allNegative
      .sort((a, b) => a.impact - b.impact)
      .slice(0, 3)
      .map(f => f.name.replace(/^Missing: /, ''));
    return `Gather these documents first: ${gatherDocs.join('; ')}.`;
  }

  const criticalMissing = allNegative
    .sort((a, b) => a.impact - b.impact)
    .slice(0, 3)
    .map(f => f.name.replace(/^Missing: /, ''));
  return `High denial risk. Required before submission: ${criticalMissing.join('; ')}.`;
}

/**
 * Score the probability of PA approval.
 *
 * @param {Object} clinicalFacts - Extracted clinical data
 * @param {Object} payerRequirements - Payer-specific requirements (from DB/cache)
 * @param {string} [payerName] - Payer name for payer-specific adjustments
 * @returns {{ probability: number, confidence: string, factors: Array, recommendation: string }}
 */
function scoreProbability(clinicalFacts, payerRequirements, payerName) {
  const cptCode = clinicalFacts?.cpt_code || payerRequirements?.cpt_code || '';

  // Resolve payer name from various sources
  const resolvedPayerName = payerName
    || payerRequirements?.payer_name
    || clinicalFacts?.payer_name
    || '';

  // Step 1: Get base approval rate
  const baseRate = getBaseApprovalRate(cptCode, resolvedPayerName);
  let score = baseRate.rate;

  // Build the factors array starting with base rate
  const allFactors = [{
    name: `Base approval rate`,
    impact: Math.round(baseRate.rate * 100),
    description: `Historical approval rate for CPT ${cptCode}: ${Math.round(baseRate.rate * 100)}% (source: ${baseRate.source}).`,
    met: true,
  }];

  // Step 2: Evaluate all risk factors
  const riskFactors = evaluateRiskFactors(clinicalFacts, resolvedPayerName, cptCode);

  // Step 3: Apply risk factor adjustments
  for (const factor of riskFactors) {
    score += factor.impact / 100;
    allFactors.push(factor);
  }

  // Clamp to 5-98% range
  score = Math.max(0.05, Math.min(0.98, score));
  const probability = Math.round(score * 100);

  // Step 4: Assess confidence
  const confidence = assessConfidence(clinicalFacts, riskFactors);

  // Step 5: Generate recommendation
  const recommendation = generateRecommendation(probability, riskFactors);

  return {
    probability,
    confidence,
    factors: allFactors,
    recommendation,
  };
}

module.exports = { scoreProbability };
