const fs = require('fs');
const path = require('path');

const SYSTEM_PROMPT_PATH = path.join(__dirname, '../prompts/justification-system.txt');
const TEMPLATES_DIR = path.join(__dirname, '../prompts/justification-templates');

const systemPrompt = fs.readFileSync(SYSTEM_PROMPT_PATH, 'utf8');

// Load specialty templates
const specialtyTemplates = {};
const templateFiles = fs.readdirSync(TEMPLATES_DIR).filter(f => f.endsWith('.txt'));
for (const file of templateFiles) {
  const name = path.basename(file, '.txt');
  specialtyTemplates[name] = fs.readFileSync(path.join(TEMPLATES_DIR, file), 'utf8');
}

// Map CPT codes to specialty templates
const CPT_SPECIALTY_MAP = {
  // Orthopedic
  '27447': 'orthopedic', '27130': 'orthopedic', '63030': 'orthopedic',
  '22612': 'orthopedic', '63650': 'orthopedic', '64483': 'orthopedic',
  '64490': 'orthopedic', '29881': 'orthopedic',
  // Neurology
  '70553': 'neurology', '72148': 'neurology', '72141': 'neurology',
  '95910': 'neurology',
  // Cardiology
  '78452': 'cardiology', '93306': 'cardiology', '93971': 'cardiology',
  // Behavioral health
  '90837': 'behavioral-health', 'J3490': 'behavioral-health',
  // General
  '95800': 'general', '43239': 'general', 'J0274': 'general',
  '97110': 'general', '77067': 'general',
};

/**
 * Select the specialty template for a given CPT code.
 */
function getSpecialtyTemplate(cptCode) {
  const specialty = CPT_SPECIALTY_MAP[cptCode] || 'general';
  return specialtyTemplates[specialty] || specialtyTemplates['general'] || '';
}

/**
 * Generate a PA justification letter from clinical facts and payer requirements.
 * Uses Claude API when available, falls back to template-based generation.
 *
 * Returns: { letter, gaps, qualityScore }
 */
async function buildJustification(clinicalFacts, payerRequirements, payerName, cptCode) {
  const startTime = Date.now();
  let letter, gaps;

  if (process.env.ANTHROPIC_API_KEY && process.env.ANTHROPIC_API_KEY !== 'your_key_here') {
    const result = await buildWithClaude(clinicalFacts, payerRequirements, payerName, cptCode);
    letter = result.letter;
    gaps = result.gaps;
  } else {
    console.log('[AI] Using demo mode justification (no API key)');
    letter = buildDemoMode(clinicalFacts, payerRequirements, payerName, cptCode);
    gaps = detectGapsDemoMode(clinicalFacts, payerRequirements);
  }

  // Run quality check
  let qualityScore;
  if (process.env.ANTHROPIC_API_KEY && process.env.ANTHROPIC_API_KEY !== 'your_key_here') {
    qualityScore = await scoreQuality(letter, clinicalFacts, payerRequirements, payerName);
  } else {
    qualityScore = scoreQualityDemoMode(letter, clinicalFacts, payerRequirements);
  }

  const elapsed = Date.now() - startTime;
  console.log(`[AI] Justification + quality check completed in ${elapsed}ms`);

  return { letter, gaps, qualityScore };
}

async function buildWithClaude(clinicalFacts, payerRequirements, payerName, cptCode) {
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic();

  const specialtyContext = getSpecialtyTemplate(cptCode || clinicalFacts?.cpt_code);
  const startTime = Date.now();
  console.log('[AI] Calling Claude for justification draft...');

  const fullSystemPrompt = `${systemPrompt}\n\n## SPECIALTY-SPECIFIC CONTEXT\n\n${specialtyContext}`;

  const requirementsText = payerRequirements
    ? formatPayerRequirements(payerRequirements)
    : 'No specific payer requirements available — use standard medical necessity criteria and relevant clinical guidelines.';

  const userMessage = `Generate a prior authorization justification letter for the following case.

PAYER: ${payerName}
CPT CODE: ${cptCode || clinicalFacts?.cpt_code || 'See documentation'}

CLINICAL FACTS (extracted from patient chart):
${JSON.stringify(clinicalFacts, null, 2)}

PAYER-SPECIFIC REQUIREMENTS FOR THIS PROCEDURE:
${requirementsText}

Generate the complete letter with all 8 sections, followed by the documentation gaps analysis.`;

  try {
    const message = await client.messages.create({
      model: 'claude-sonnet-4-5',
      max_tokens: 2500,
      temperature: 0.3,
      system: fullSystemPrompt,
      messages: [{ role: 'user', content: userMessage }],
    });

    const elapsed = Date.now() - startTime;
    console.log(`[AI] Claude justification completed in ${elapsed}ms`);

    const fullText = message.content[0].text;
    return parseLetterAndGaps(fullText);
  } catch (err) {
    console.error('[AI] Claude justification failed:', err.message);
    const letter = buildDemoMode(clinicalFacts, payerRequirements, payerName, cptCode);
    const gaps = detectGapsDemoMode(clinicalFacts, payerRequirements);
    return { letter, gaps };
  }
}

/**
 * Parse Claude's response into letter body and gaps section.
 */
function parseLetterAndGaps(fullText) {
  const gapMarker = 'DOCUMENTATION GAPS DETECTED:';
  const gapIndex = fullText.indexOf(gapMarker);

  if (gapIndex === -1) {
    return { letter: fullText.trim(), gaps: [] };
  }

  const letter = fullText.substring(0, gapIndex).replace(/---\s*$/, '').trim();
  const gapsText = fullText.substring(gapIndex + gapMarker.length).replace(/---\s*$/, '').trim();

  const gaps = gapsText
    .split('\n')
    .map(line => line.replace(/^[-•*]\s*/, '').trim())
    .filter(line => line.length > 0 && !line.startsWith('---'));

  return { letter, gaps };
}

/**
 * Format payer requirements for the prompt.
 */
function formatPayerRequirements(req) {
  const parts = [];

  if (req.criteria && Array.isArray(req.criteria)) {
    parts.push('REQUIRED CRITERIA:');
    req.criteria.forEach((c, i) => {
      const desc = typeof c === 'string' ? c : c.description || JSON.stringify(c);
      const required = typeof c === 'object' && c.required === false ? ' (optional)' : ' (REQUIRED)';
      parts.push(`  ${i + 1}. ${desc}${required}`);
    });
  }

  if (req.supporting_docs_required || req.supporting_docs) {
    const docs = req.supporting_docs_required || req.supporting_docs || [];
    if (docs.length > 0) {
      parts.push(`\nREQUIRED SUPPORTING DOCUMENTS: ${docs.join(', ')}`);
    }
  }

  if (req.clinical_guidelines && req.clinical_guidelines.length > 0) {
    parts.push(`\nREFERENCED CLINICAL GUIDELINES: ${req.clinical_guidelines.join('; ')}`);
  }

  if (req.common_denial_reasons && req.common_denial_reasons.length > 0) {
    parts.push(`\nCOMMON DENIAL REASONS TO PREEMPT:`);
    req.common_denial_reasons.forEach(r => parts.push(`  - ${r}`));
  }

  if (req.tips) {
    parts.push(`\nPAYER TIP: ${req.tips}`);
  }

  return parts.join('\n') || 'Standard medical necessity criteria apply.';
}

/**
 * Quality scoring — second Claude call to evaluate the letter.
 */
async function scoreQuality(letter, clinicalFacts, payerRequirements, payerName) {
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic();

  console.log('[AI] Running quality check on justification letter...');

  const prompt = `You are a PA letter quality reviewer. Score this prior authorization justification letter on three dimensions (1-10 each):

1. COMPLETENESS: Does it include all 8 required sections? Does each section have substantive content?
2. PAYER-SPECIFICITY: Does it directly address the payer's known requirements? Does it use payer-appropriate language?
3. CLINICAL ACCURACY: Does it accurately reflect the clinical facts provided? Does it avoid fabricating information?

LETTER TO REVIEW:
${letter}

CLINICAL FACTS PROVIDED:
${JSON.stringify(clinicalFacts, null, 2)}

PAYER: ${payerName}
${payerRequirements ? `PAYER REQUIREMENTS:\n${JSON.stringify(payerRequirements.criteria || [], null, 2)}` : 'No specific payer requirements provided.'}

Respond in EXACTLY this JSON format (no markdown, no explanation):
{"completeness": <number>, "payer_specificity": <number>, "clinical_accuracy": <number>, "overall": <number>, "suggestions": ["suggestion 1", "suggestion 2"]}

The "overall" score should be a weighted average: completeness (30%) + payer_specificity (35%) + clinical_accuracy (35%).
Only include suggestions if overall < 7.`;

  try {
    const message = await client.messages.create({
      model: 'claude-sonnet-4-5',
      max_tokens: 500,
      temperature: 0.1,
      messages: [{ role: 'user', content: prompt }],
    });

    const text = message.content[0].text.trim();
    // Try to parse JSON from the response
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const score = JSON.parse(jsonMatch[0]);
      console.log(`[AI] Quality score: ${score.overall}/10`);
      return score;
    }
  } catch (err) {
    console.error('[AI] Quality scoring failed:', err.message);
  }

  // Fallback
  return scoreQualityDemoMode(letter, clinicalFacts, payerRequirements);
}

/**
 * Demo mode quality scoring (rule-based).
 */
function scoreQualityDemoMode(letter, clinicalFacts, payerRequirements) {
  let completeness = 5;
  let payerSpecificity = 5;
  let clinicalAccuracy = 5;
  const suggestions = [];

  // Check section completeness
  const sections = [
    'PATIENT INFORMATION', 'PROCEDURE REQUESTED', 'CLINICAL HISTORY',
    'PRIOR TREATMENT', 'MEDICAL NECESSITY', 'SUPPORTING CLINICAL EVIDENCE',
    'EXPECTED OUTCOME', 'PHYSICIAN ATTESTATION',
  ];
  const foundSections = sections.filter(s => letter.toUpperCase().includes(s));
  completeness = Math.min(10, 4 + foundSections.length * 0.75);

  // Check payer specificity
  if (payerRequirements?.criteria) {
    const criteria = payerRequirements.criteria;
    let addressed = 0;
    for (const c of criteria) {
      const desc = typeof c === 'string' ? c : c.description || '';
      const keywords = desc.toLowerCase().split(/\s+/).filter(w => w.length > 4);
      const matched = keywords.some(kw => letter.toLowerCase().includes(kw));
      if (matched) addressed++;
    }
    payerSpecificity = criteria.length > 0
      ? Math.min(10, 4 + (addressed / criteria.length) * 6)
      : 6;
  }

  // Check clinical accuracy — look for key facts
  if (clinicalFacts) {
    let factsReferenced = 0;
    const checks = [
      clinicalFacts.primary_diagnosis,
      clinicalFacts.cpt_code,
      ...(clinicalFacts.icd10_codes || []),
      clinicalFacts.severity,
    ].filter(Boolean);
    for (const fact of checks) {
      if (letter.includes(String(fact))) factsReferenced++;
    }
    clinicalAccuracy = checks.length > 0
      ? Math.min(10, 5 + (factsReferenced / checks.length) * 5)
      : 7;
  }

  const overall = parseFloat((completeness * 0.3 + payerSpecificity * 0.35 + clinicalAccuracy * 0.35).toFixed(1));

  if (overall < 7) {
    if (completeness < 7) suggestions.push('Add missing letter sections for a more complete justification');
    if (payerSpecificity < 7) suggestions.push('More directly address payer-specific requirements in the letter');
    if (clinicalAccuracy < 7) suggestions.push('Include more specific clinical data points from the patient record');
  }

  return { completeness: Math.round(completeness * 10) / 10, payer_specificity: Math.round(payerSpecificity * 10) / 10, clinical_accuracy: Math.round(clinicalAccuracy * 10) / 10, overall, suggestions };
}

/**
 * Detect gaps in demo mode.
 */
function detectGapsDemoMode(clinicalFacts, payerRequirements) {
  const gaps = [];

  if (!payerRequirements?.criteria) return gaps;

  const criteria = payerRequirements.criteria;
  const facts = clinicalFacts || {};

  for (const c of criteria) {
    const desc = typeof c === 'string' ? c : c.description || '';
    const category = typeof c === 'object' ? c.category : '';
    const lower = (desc + ' ' + category).toLowerCase();

    let met = false;

    if (lower.includes('conservative') || lower.includes('physical therapy') || lower.includes('pt ')) {
      met = (facts.prior_treatments || []).length > 0;
    } else if (lower.includes('imaging') || lower.includes('radiograph') || lower.includes('mri')) {
      met = !!(facts.imaging_results || facts.prior_imaging);
    } else if (lower.includes('lab') || lower.includes('blood') || lower.includes('a1c')) {
      met = !!(facts.lab_results);
    } else if (lower.includes('symptom') || lower.includes('duration')) {
      met = !!(facts.duration_weeks || facts.symptoms?.length > 0);
    } else if (lower.includes('medication') || lower.includes('pharmacolog')) {
      met = !!(facts.medications?.length > 0 || facts.prior_treatments?.some(t =>
        t.treatment?.toLowerCase().includes('medication') || t.treatment?.toLowerCase().includes('nsaid')
      ));
    } else if (lower.includes('functional') || lower.includes('daily') || lower.includes('limitation')) {
      met = !!(facts.functional_limitations || facts.provider_assessment);
    } else {
      // Default: check if any clinical data exists
      met = Object.keys(facts).length > 3;
    }

    if (!met) {
      gaps.push(`${desc} — not clearly documented in available clinical notes`);
    }
  }

  return gaps;
}

/**
 * Demo mode letter generation with all 8 sections.
 */
function buildDemoMode(clinicalFacts, payerRequirements, payerName, cptCode) {
  const facts = clinicalFacts || {};
  const diagnosis = facts.primary_diagnosis || 'See clinical documentation';
  const icdCodes = (facts.icd10_codes || []).join(', ') || 'See documentation';
  const code = cptCode || facts.cpt_code || 'See documentation';
  const symptoms = (facts.symptoms || []).join(', ') || 'See clinical notes';
  const duration = facts.duration_weeks ? `${facts.duration_weeks} weeks` : 'See clinical notes';
  const severity = facts.severity || 'moderate';

  const treatments = (facts.prior_treatments || [])
    .map(t => `- ${t.treatment || t} (${t.duration || 'duration per records'}): ${t.outcome || 'See documentation'}`)
    .join('\n') || '- Conservative management per clinical documentation';

  const payerCriteria = payerRequirements?.criteria
    ? payerRequirements.criteria.map(c => {
        const desc = typeof c === 'string' ? c : c.description || JSON.stringify(c);
        return `  - ${desc}: ADDRESSED — See clinical history and treatment documentation above.`;
      }).join('\n')
    : '  - Standard medical necessity criteria: ADDRESSED per clinical documentation.';

  const guidelines = payerRequirements?.clinical_guidelines
    ? payerRequirements.clinical_guidelines.join('; ')
    : 'Current evidence-based clinical practice guidelines';

  return `PRIOR AUTHORIZATION JUSTIFICATION LETTER
${'='.repeat(50)}

Date: ${new Date().toISOString().split('T')[0]}
To: ${payerName} — Prior Authorization Department
Re: Authorization Request for CPT ${code}

--- 1. PATIENT INFORMATION ---
Patient ID: ${facts.patient_id || '[See chart]'}
Primary Diagnosis: ${diagnosis}
ICD-10 Code(s): ${icdCodes}
Date of Request: ${new Date().toISOString().split('T')[0]}

--- 2. PROCEDURE REQUESTED ---
CPT Code: ${code}
Clinical Indication: ${diagnosis}
The above procedure is requested to evaluate and/or treat the patient's documented condition as detailed below.

--- 3. CLINICAL HISTORY ---
The patient presents with ${symptoms} of approximately ${duration} duration. Condition severity is assessed as ${severity}. ${facts.provider_assessment || ''} ${facts.functional_limitations ? `Functional impact: ${facts.functional_limitations}.` : 'The patient reports significant functional limitations affecting daily activities.'}

${facts.physical_exam ? `Physical Examination: ${facts.physical_exam}` : ''}
${facts.imaging_results ? `Imaging: ${facts.imaging_results}` : ''}

--- 4. PRIOR TREATMENT ATTEMPTS & OUTCOMES ---
The following conservative treatments have been attempted:
${treatments}

Despite the above interventions, the patient has not achieved adequate symptom relief or functional improvement, necessitating the requested procedure.

--- 5. MEDICAL NECESSITY STATEMENT ---
The requested procedure (CPT ${code}) is medically necessary because the patient has exhausted appropriate conservative treatment options without achieving clinically meaningful improvement. This recommendation is consistent with ${guidelines}.

${payerName} criteria for this procedure have been addressed as follows:
${payerCriteria}

The patient's clinical presentation meets established indications for this procedure based on documented symptom severity, duration, failed conservative management, and objective clinical findings.

--- 6. SUPPORTING CLINICAL EVIDENCE ---
Physical Examination: ${facts.physical_exam || 'See clinical notes in attached documentation'}
Diagnostic Results: ${facts.imaging_results || facts.lab_results || 'See attached documentation'}
${facts.medications ? `Current Medications: ${Array.isArray(facts.medications) ? facts.medications.join(', ') : facts.medications}` : ''}

--- 7. EXPECTED OUTCOME & ALTERNATIVES CONSIDERED ---
The requested procedure is expected to provide significant clinical improvement including pain reduction, improved function, and enhanced quality of life. Evidence-based literature supports favorable outcomes for this procedure in patients with similar clinical presentations.

Without intervention, the patient's condition is expected to continue to decline, leading to increased disability, potential complications, and likely need for more invasive or costly treatment.

Alternative treatments considered include continued conservative management, which has proven inadequate as documented above.

--- 8. PHYSICIAN ATTESTATION ---
I attest that the information provided above is accurate and complete to the best of my knowledge. The requested procedure is medically necessary for this patient based on my clinical evaluation and review of all available medical records.

I am available for peer-to-peer review at the convenience of ${payerName}'s medical director to discuss this case further.

Respectfully submitted,
[Treating Physician], MD
[Practice Name]
NPI: [Provider NPI]
Phone: [Contact Number]
Fax: [Fax Number]`;
}

module.exports = { buildJustification, scoreQuality, scoreQualityDemoMode, getSpecialtyTemplate };
