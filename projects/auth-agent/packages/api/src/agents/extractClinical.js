const fs = require('fs');
const path = require('path');

const PROMPT_PATH = path.join(__dirname, '../prompts/extractClinical.txt');
const systemPrompt = fs.readFileSync(PROMPT_PATH, 'utf8');

/**
 * Extract structured clinical facts from raw clinical note text.
 * Uses Claude API when available, falls back to rule-based extraction in demo mode.
 */
async function extractClinical(pdfText) {
  // PHI: treat as sensitive
  if (!pdfText || pdfText.trim().length === 0) {
    throw new Error('No clinical text provided');
  }

  // Try Claude API first
  if (process.env.ANTHROPIC_API_KEY && process.env.ANTHROPIC_API_KEY !== 'your_key_here') {
    return await extractWithClaude(pdfText);
  }

  // Fallback: rule-based extraction for demo mode
  console.log('[AI] Using demo mode extraction (no API key)');
  return extractDemoMode(pdfText);
}

async function extractWithClaude(text) {
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic();

  const startTime = Date.now();
  console.log('[AI] Calling Claude for clinical extraction...');

  try {
    const message = await client.messages.create({
      model: 'claude-sonnet-4-5',
      max_tokens: 2000,
      temperature: 0.1,
      system: systemPrompt,
      messages: [
        {
          role: 'user',
          content: `Extract clinical facts from the following medical document:\n\n${text}`,
        },
      ],
    });

    const elapsed = Date.now() - startTime;
    console.log(`[AI] Claude extraction completed in ${elapsed}ms`);

    const responseText = message.content[0].text;
    // Strip markdown code fences if Claude wraps the JSON
    const cleaned = responseText.replace(/^```(?:json)?\s*/i, '').replace(/\s*```\s*$/i, '').trim();
    return JSON.parse(cleaned);
  } catch (err) {
    console.error('[AI] Claude extraction failed:', err.message);
    // Fall back to demo mode
    return extractDemoMode(text);
  }
}

function extractDemoMode(text) {
  const lower = text.toLowerCase();

  // Simple pattern matching for demo
  const icd10Pattern = /[A-Z]\d{2}\.?\d{0,4}/g;
  const cptPattern = /(?:CPT|cpt)\s*:?\s*(\d{5})/;
  const icd10Codes = text.match(icd10Pattern) || [];
  const cptMatch = text.match(cptPattern);

  return {
    primary_diagnosis: extractBetween(text, 'ASSESSMENT', '\n') || extractBetween(text, 'DIAGNOSIS', '\n') || 'See clinical notes',
    secondary_diagnoses: [],
    icd10_codes: [...new Set(icd10Codes)],
    symptoms: extractSymptoms(lower),
    duration_weeks: extractDuration(lower),
    severity: lower.includes('severe') ? 'severe' : lower.includes('moderate') ? 'moderate' : 'mild',
    prior_treatments: extractTreatments(lower),
    medications: extractMedications(text),
    imaging_results: lower.includes('mri') || lower.includes('imaging') || lower.includes('x-ray')
      ? 'See imaging section in clinical notes'
      : null,
    lab_results: null,
    physical_exam: extractBetween(text, 'PHYSICAL EXAMINATION', 'ASSESSMENT') || extractBetween(text, 'EXAM', 'PLAN') || null,
    provider_assessment: extractBetween(text, 'ASSESSMENT', 'PLAN') || null,
    requested_procedure: extractBetween(text, 'PLAN', '\n\n') || 'See clinical notes',
    cpt_code: cptMatch ? cptMatch[1] : null,
    missing_info: [],
  };
}

function extractBetween(text, start, end) {
  const startIdx = text.indexOf(start);
  if (startIdx === -1) return null;
  const afterStart = text.substring(startIdx + start.length);
  const endIdx = end === '\n' ? afterStart.indexOf('\n') : afterStart.indexOf(end);
  if (endIdx === -1) return afterStart.trim().substring(0, 200);
  return afterStart.substring(0, endIdx).trim().substring(0, 200);
}

function extractSymptoms(text) {
  const symptoms = [];
  const symptomWords = ['pain', 'numbness', 'tingling', 'weakness', 'fatigue', 'headache', 'swelling', 'stiffness', 'sleepiness', 'apnea'];
  for (const word of symptomWords) {
    if (text.includes(word)) symptoms.push(word);
  }
  return symptoms;
}

function extractDuration(text) {
  const weekMatch = text.match(/(\d+)\s*weeks?/);
  const monthMatch = text.match(/(\d+)\s*months?/);
  const yearMatch = text.match(/(\d+)\s*years?/);
  if (weekMatch) return parseInt(weekMatch[1]);
  if (monthMatch) return parseInt(monthMatch[1]) * 4;
  if (yearMatch) return parseInt(yearMatch[1]) * 52;
  return null;
}

function extractTreatments(text) {
  const treatments = [];
  const treatmentWords = ['physical therapy', 'pt', 'nsaids', 'injection', 'medication', 'brace', 'surgery', 'conservative'];
  for (const word of treatmentWords) {
    if (text.includes(word)) {
      treatments.push({ treatment: word, duration: 'see notes', outcome: 'failed' });
    }
  }
  return treatments;
}

function extractMedications(text) {
  const meds = [];
  const medNames = ['ibuprofen', 'naproxen', 'gabapentin', 'pregabalin', 'prednisone', 'metformin', 'lisinopril', 'amlodipine', 'sumatriptan', 'topiramate', 'sertraline', 'fluoxetine', 'duloxetine', 'aripiprazole', 'ozempic', 'semaglutide'];
  const lower = text.toLowerCase();
  for (const med of medNames) {
    if (lower.includes(med)) meds.push(med);
  }
  return meds;
}

module.exports = { extractClinical };
