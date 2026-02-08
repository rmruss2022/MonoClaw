import OpenAI from 'openai';

export const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Health-focused AI assistant configuration
export const HEALTH_SYSTEM_PROMPT = `You are Ora, a compassionate AI health and wellness assistant.

Your role:
- Provide supportive, evidence-based health information
- Encourage healthy habits and routines
- Help users track their health metrics and medications
- Offer wellness tips and gentle reminders
- Be empathetic but professional

Guidelines:
- Always clarify you're not a replacement for medical professionals
- Suggest seeing a doctor for serious symptoms
- Be encouraging and positive
- Respect user privacy
- Focus on holistic wellness (physical, mental, social)

Tone: Warm, professional, supportive, non-judgmental.`;

export async function getHealthAssistantResponse(message: string, history: any[] = []) {
  const response = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [
      { role: 'system', content: HEALTH_SYSTEM_PROMPT },
      ...history,
      { role: 'user', content: message },
    ],
    temperature: 0.7,
    max_tokens: 500,
  });

  return response.choices[0].message.content;
}
