const fs = require('fs');
const path = require('path');

const SYSTEM_PROMPT_PATH = path.join(__dirname, '../prompts/appeal-system.txt');
const CARC_STRATEGIES_PATH = path.join(__dirname, '../../../../src/data/carcStrategies.json');

const systemPrompt = fs.readFileSync(SYSTEM_PROMPT_PATH, 'utf8');
const carcStrategies = JSON.parse(fs.readFileSync(CARC_STRATEGIES_PATH, 'utf8'));

/**
 * Look up the CARC strategy for a given denial reason code.
 * Handles codes like "CO-50", "CO50", "50", etc.
 */
function getCarcStrategy(denialReasonCode) {
  if (!denialReasonCode) return null;
  const normalized = denialReasonCode.trim().toUpperCase();
  return carcStrategies.find(s => {
    const stratCode = s.code.toUpperCase();
    return stratCode === normalized
      || stratCode.replace('-', '') === normalized.replace('-', '')
      || stratCode.split('-')[1] === normalized;
  }) || null;
}

/**
 * Calculate the appeal deadline based on payer rules and denial date.
 * Most commercial payers: 180 days. Medicare: 120 days. Medicaid: 60 days.
 * Urgency: first appeal should be filed within 30 days for best results.
 */
function calculateDeadline(denialDate, payerName) {
  const denial = denialDate ? new Date(denialDate) : new Date();
  const name = (payerName || '').toLowerCase();

  let daysAllowed = 180; // default commercial
  if (name.includes('medicare')) daysAllowed = 120;
  if (name.includes('medicaid')) daysAllowed = 60;

  const deadline = new Date(denial);
  deadline.setDate(deadline.getDate() + daysAllowed);
  return deadline;
}

/**
 * Draft an appeal letter for a denied PA.
 *
 * @param {object} params
 * @param {object} params.originalPA - The original PA request object
 * @param {string} params.denialReasonCode - CARC denial code (e.g. "CO-50")
 * @param {string} params.denialReasonText - Human-readable denial reason
 * @param {string} params.payerName - Name of the insurance payer
 * @returns {{ appealLetter, appealType, escalationRecommended, deadlineDate, carcStrategy }}
 */
async function draftAppeal({ originalPA, denialReasonCode, denialReasonText, payerName }) {
  const carcStrategy = getCarcStrategy(denialReasonCode);
  const deadlineDate = calculateDeadline(originalPA.decision_at, payerName);

  let appealLetter, appealType, escalationRecommended;

  if (process.env.ANTHROPIC_API_KEY && process.env.ANTHROPIC_API_KEY !== 'your_key_here') {
    const result = await buildWithClaude({ originalPA, denialReasonCode, denialReasonText, payerName, carcStrategy, deadlineDate });
    appealLetter = result.appealLetter;
    appealType = result.appealType;
    escalationRecommended = result.escalationRecommended;
  } else {
    console.log('[Appeal] Using demo mode (no API key)');
    const result = buildDemoMode({ originalPA, denialReasonCode, denialReasonText, payerName, carcStrategy, deadlineDate });
    appealLetter = result.appealLetter;
    appealType = result.appealType;
    escalationRecommended = result.escalationRecommended;
  }

  return {
    appealLetter,
    appealType,
    escalationRecommended,
    deadlineDate: deadlineDate.toISOString(),
    carcStrategy,
  };
}

async function buildWithClaude({ originalPA, denialReasonCode, denialReasonText, payerName, carcStrategy, deadlineDate }) {
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic();

  const clinicalExtract = originalPA.clinical_extract || {};
  const originalJustification = originalPA.justification_final || originalPA.justification_draft || '';

  const strategyContext = carcStrategy
    ? `
CARC STRATEGY FOR ${carcStrategy.code} (${carcStrategy.name}):
Strategy: ${carcStrategy.strategy}
Required Evidence: ${carcStrategy.required_evidence.join('; ')}
Historical Success Rate: ${carcStrategy.success_rate_estimate}%
Typical Resolution: ${carcStrategy.typical_resolution_days} days
Escalation Path: ${carcStrategy.escalation_path}`
    : 'No specific CARC strategy available — use general medical necessity appeal approach.';

  const userMessage = `Draft an appeal letter for the following denied prior authorization.

DENIAL INFORMATION:
- Denial Reason Code: ${denialReasonCode || 'Not specified'}
- Denial Reason Text: ${denialReasonText || 'Not specified'}
- Payer: ${payerName}
- Appeal Deadline: ${deadlineDate.toISOString().split('T')[0]}
- CPT Code: ${originalPA.cpt_code}
- ICD-10 Codes: ${(originalPA.icd10_codes || []).join(', ')}

${strategyContext}

ORIGINAL CLINICAL FACTS:
${JSON.stringify(clinicalExtract, null, 2)}

ORIGINAL JUSTIFICATION LETTER:
${originalJustification}

Generate a compelling appeal letter that directly addresses the ${denialReasonCode || 'denial'} reason code, strengthens the original clinical justification, and cites specific clinical guidelines and peer-reviewed evidence.`;

  try {
    console.log('[Appeal] Calling Claude for appeal draft...');
    const startTime = Date.now();

    const message = await client.messages.create({
      model: 'claude-sonnet-4-5',
      max_tokens: 3000,
      temperature: 0.3,
      system: systemPrompt,
      messages: [{ role: 'user', content: userMessage }],
    });

    const elapsed = Date.now() - startTime;
    console.log(`[Appeal] Claude appeal draft completed in ${elapsed}ms`);

    const fullText = message.content[0].text;
    return parseAppealResponse(fullText);
  } catch (err) {
    console.error('[Appeal] Claude appeal failed:', err.message);
    return buildDemoMode({ originalPA, denialReasonCode, denialReasonText, payerName, carcStrategy, deadlineDate });
  }
}

/**
 * Parse Claude's response into appeal letter and metadata.
 */
function parseAppealResponse(fullText) {
  const metadataMarker = 'APPEAL_METADATA:';
  const markerIndex = fullText.indexOf(metadataMarker);

  let appealLetter = fullText;
  let appealType = 'first_level';
  let escalationRecommended = false;

  if (markerIndex !== -1) {
    appealLetter = fullText.substring(0, fullText.lastIndexOf('---', markerIndex)).trim();
    const metadataText = fullText.substring(markerIndex + metadataMarker.length).trim();

    try {
      const jsonMatch = metadataText.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const metadata = JSON.parse(jsonMatch[0]);
        appealType = metadata.appeal_type || 'first_level';
        escalationRecommended = metadata.escalation_recommended || false;
      }
    } catch {
      // Use defaults
    }
  }

  return { appealLetter, appealType, escalationRecommended };
}

/**
 * Demo mode appeal letter generation.
 */
function buildDemoMode({ originalPA, denialReasonCode, denialReasonText, payerName, carcStrategy, deadlineDate }) {
  const facts = originalPA.clinical_extract || {};
  const diagnosis = facts.primary_diagnosis || 'See clinical documentation';
  const icdCodes = (originalPA.icd10_codes || facts.icd10_codes || []).join(', ') || 'See documentation';
  const cptCode = originalPA.cpt_code || facts.cpt_code || 'See documentation';
  const originalLetter = originalPA.justification_final || originalPA.justification_draft || '';

  const treatments = (facts.prior_treatments || [])
    .map(t => `  - ${t.treatment || t} (${t.duration || 'see records'}): ${t.outcome || 'failed to provide adequate relief'}`)
    .join('\n') || '  - Conservative management per clinical documentation';

  const strategySection = carcStrategy
    ? `
Per our analysis of ${carcStrategy.code} denials, appeals with strong clinical evidence achieve a ${carcStrategy.success_rate_estimate}% overturn rate. The required evidence for this appeal type includes:
${carcStrategy.required_evidence.map(e => `  - ${e}`).join('\n')}

Each of these evidence requirements is addressed in this appeal as detailed below.`
    : '';

  const escalationNote = carcStrategy
    ? `\nEscalation Path: ${carcStrategy.escalation_path}`
    : '';

  const appealLetter = `APPEAL OF PRIOR AUTHORIZATION DENIAL
${'='.repeat(50)}

Date: ${new Date().toISOString().split('T')[0]}
To: ${payerName} — Appeals and Grievances Department
Re: Appeal of Prior Authorization Denial
    CPT Code: ${cptCode}
    Denial Reason: ${denialReasonCode || 'Not specified'} — ${denialReasonText || 'Not specified'}
    Appeal Deadline: ${deadlineDate.toISOString().split('T')[0]}

--- 1. STATEMENT OF APPEAL ---

Dear Appeals Review Committee,

I am writing to formally appeal the denial of prior authorization for CPT ${cptCode} (ICD-10: ${icdCodes}) for patient ${originalPA.patient_id || '[See chart]'}.

The authorization was denied with reason code ${denialReasonCode || 'unspecified'}: "${denialReasonText || 'Not medically necessary'}". After thorough review of the clinical documentation and applicable medical guidelines, we believe this denial was made in error and respectfully request immediate reconsideration.

--- 2. DENIAL REBUTTAL ---

${denialReasonCode === 'CO-50' || !denialReasonCode ? `The denial states that the requested procedure is "not medically necessary." We strongly disagree with this determination. As documented below, the patient has:

1. Exhausted appropriate conservative treatment options over an adequate trial period
2. Demonstrated progressive clinical deterioration despite treatment
3. Met all published clinical criteria for the requested procedure
4. Been evaluated and recommended for this procedure by a board-certified specialist

The clinical evidence overwhelmingly supports the medical necessity of this procedure for this patient.` : ''}${denialReasonCode === 'CO-4' ? `The denial indicates an invalid procedure code. We have verified that CPT ${cptCode} accurately reflects the planned procedure as documented in the clinical notes. The code selection is consistent with CPT coding guidelines and the procedure described in the operative plan.` : ''}${denialReasonCode === 'CO-197' ? `The denial states no precertification was on file. We have records showing that authorization was requested on the appropriate date. Attached please find documentation of our authorization request submission.` : ''}${denialReasonCode === 'CO-16' ? `The denial indicates missing information. We have compiled a comprehensive documentation package addressing all information requirements. All previously missing items are now included in this appeal submission.` : ''}${denialReasonCode === 'CO-119' ? `The denial states the benefit maximum has been reached. We are requesting a medical exception based on the patient's continued clinical need. Discontinuation of treatment at this point would result in clinical deterioration and likely more costly interventions.` : ''}${denialReasonCode === 'CO-96' ? `The denial indicates the service is non-covered. We believe this determination is inconsistent with the patient's plan benefits and applicable coverage requirements.` : ''}${denialReasonCode === 'PR-204' ? `The denial assigns this as member responsibility. We are requesting a medical exception based on the unique clinical circumstances of this case and the absence of adequate covered alternative treatments.` : ''}${denialReasonCode === 'CO-170' ? `The denial indicates the diagnosis does not support the service. The clinical documentation clearly establishes the relationship between the patient's diagnosis and the medical necessity of the requested procedure.` : ''}${denialReasonCode === 'CO-151' ? `The denial reflects a payment adjustment. The clinical documentation supports the full scope and complexity of the service as billed.` : ''}${denialReasonCode === 'CO-22' ? `The denial indicates coordination of benefits issues. We have verified the patient's insurance coverage and confirmed that ${payerName} is the appropriate payer for this claim.` : ''}
${strategySection}

--- 3. STRENGTHENED CLINICAL JUSTIFICATION ---

Patient Presentation:
The patient presents with ${diagnosis} of ${facts.severity || 'significant'} severity${facts.duration_weeks ? `, with symptoms persisting for ${facts.duration_weeks} weeks` : ''}. ${facts.provider_assessment || 'The treating physician has determined that the current conservative management approach is inadequate.'} ${facts.functional_limitations ? `The patient reports: ${facts.functional_limitations}.` : 'The patient experiences significant functional limitations affecting daily activities and quality of life.'}

${facts.physical_exam ? `Physical Examination Findings:\n${facts.physical_exam}\n` : ''}${facts.imaging_results ? `Diagnostic Imaging:\n${facts.imaging_results}\n` : ''}

Conservative Treatment History:
The following treatments have been attempted and have failed to provide adequate clinical improvement:
${treatments}

Despite exhaustive conservative management, the patient's condition has not improved, necessitating the requested intervention.

--- 4. CLINICAL GUIDELINES CITATION ---

The medical necessity of this procedure is supported by the following clinical guidelines and evidence:

1. MCG Care Guidelines (24th Edition) — The patient meets criteria for ${cptCode} based on documented failure of conservative treatment, objective clinical findings, and progressive functional decline.

2. Peer-Reviewed Evidence — Multiple studies published in peer-reviewed journals support the efficacy of this procedure for patients with this clinical presentation:
   - Systematic reviews demonstrate significant improvement in functional outcomes and pain reduction
   - Long-term follow-up studies confirm durable clinical benefit
   - Comparative effectiveness research supports this intervention over continued conservative management

3. Specialty Society Guidelines — The relevant medical specialty society guidelines recommend this procedure for patients meeting the clinical criteria demonstrated by this patient.

--- 5. PAYER POLICY REFERENCE ---

${payerName}'s own published clinical coverage policy for CPT ${cptCode} states that authorization should be granted when:
  - Conservative treatment has been attempted and failed (DOCUMENTED ABOVE)
  - Clinical documentation supports medical necessity (PROVIDED)
  - The procedure is appropriate for the patient's diagnosis (CONFIRMED)

We submit that all of ${payerName}'s stated coverage criteria have been met.

--- 6. PATIENT-SPECIFIC CLINICAL NECESSITY ---

This is not a routine or elective request. This specific patient requires this specific procedure because:

1. All appropriate conservative treatments have been exhausted over an adequate trial period
2. The patient's condition is ${facts.severity || 'progressively worsening'} and clinically deteriorating
3. Delaying intervention risks further clinical decline, increased disability, and potential need for more invasive/costly procedures
4. The treating specialist has determined that this is the most appropriate next step in the patient's care plan

--- 7. REQUEST FOR RECONSIDERATION ---

Based on the clinical evidence presented above, we respectfully request that ${payerName} overturn the denial and authorize CPT ${cptCode} for this patient.

If this first-level appeal is not approved, we formally request:
  1. A peer-to-peer review with ${payerName}'s medical director
  2. Written explanation of specific clinical criteria not met
  3. Identification of what additional documentation would be needed
${escalationNote}

This appeal must be resolved by ${deadlineDate.toISOString().split('T')[0]} per applicable appeal timeline requirements.

I am available for peer-to-peer discussion at any time to review this case.

Respectfully submitted,
[Treating Physician], MD
[Practice Name]
NPI: [Provider NPI]
Phone: [Contact Number]
Fax: [Fax Number]`;

  // Determine appeal type and escalation
  const escalationRecommended = carcStrategy
    ? carcStrategy.success_rate_estimate < 50
    : false;

  return {
    appealLetter,
    appealType: 'first_level',
    escalationRecommended,
  };
}

module.exports = { draftAppeal, getCarcStrategy, calculateDeadline, carcStrategies };
