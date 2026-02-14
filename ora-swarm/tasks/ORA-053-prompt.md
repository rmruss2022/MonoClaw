You are a Content-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-053 - Write intake quiz questions and answer options
PRIORITY: High (P1) - blocks quiz UI implementation
ESTIMATED HOURS: 4

DESCRIPTION:
Write 10 high-quality, thoughtful intake quiz questions for the Ora AI wellness app's onboarding flow. These questions will be presented to new users to personalize their experience. The quiz should feel warm, empathetic, and non-judgmental - like a first conversation with a compassionate counselor.

APP CONTEXT:
Ora AI is a wellness/mental health companion app. It offers:
- Free-form chat with an AI companion
- Guided journaling prompts
- Guided exercises (CBT, mindfulness, etc.)
- Progress analysis and insights
- Weekly planning and goal setting
- Meditation and breathing exercises
- Community forum (letters system)

The quiz data will be used to:
- Personalize the AI companion's approach
- Suggest appropriate behaviors/modes
- Set check-in frequency preferences
- Understand user's wellness background
- Tailor content recommendations

DELIVERABLES:

1. **Quiz Questions Document** at /Users/matthew/Desktop/Feb26/ora-ai/docs/content/intake-quiz.md:
   - 10 questions with full answer options
   - Question type specified (single-select, multi-select, slider, open-ended)
   - For each question: rationale for inclusion and how data is used for personalization
   - Suggested order/flow
   - Intro text and transition copy between sections

2. **Quiz Data Schema** at /Users/matthew/Desktop/Feb26/ora-ai/docs/content/quiz-data-schema.json:
   - JSON structure for storing quiz responses
   - Field names, types, and possible values
   - Ready for backend integration

3. **Personalization Mapping** at /Users/matthew/Desktop/Feb26/ora-ai/docs/content/personalization-mapping.md:
   - How each answer maps to app personalization
   - Which behaviors to suggest based on responses
   - Check-in frequency recommendations
   - Content tone adjustments

THE 10 QUESTIONS:

Q1: "What brings you to Ora?" (multi-select)
   - Managing stress or anxiety
   - Personal growth and self-discovery
   - Building better habits
   - Improving relationships
   - Processing difficult emotions
   - General wellness and mindfulness
   - Other (with text input)

Q2: "What area of your life could use the most attention right now?" (single-select)
   - Work and career
   - Relationships and social connections
   - Physical health and wellness
   - Personal growth and learning
   - Emotional well-being
   - Finding purpose and meaning

Q3: "How do you prefer to reflect and process?" (multi-select)
   - Writing and journaling
   - Talking things through
   - Guided exercises and prompts
   - Meditation and mindfulness
   - Physical activity
   - Creative expression

Q4: "What's your biggest challenge right now?" (open-ended text)
   - Placeholder: "There are no wrong answers here..."
   - Max 500 characters
   - Optional skip button

Q5: "How often would you like to check in with Ora?" (single-select)
   - Every day (I'm committed!)
   - A few times a week (steady pace)
   - Once a week (keeping it light)
   - When I feel like it (no pressure)

Q6: "What time works best for your wellness practice?" (single-select)
   - Morning (fresh start)
   - Afternoon (midday reset)
   - Evening (wind down)
   - It varies (surprise me!)

Q7: "Have you worked with a therapist or counselor before?" (single-select)
   - Yes, I currently do
   - Yes, in the past
   - No, but I'm interested
   - No, and I prefer self-guided
   - Prefer not to say

Q8: "How would you rate your current stress level?" (slider 1-10)
   - 1 = "Very calm and centered"
   - 5 = "Managing but could be better"
   - 10 = "Feeling overwhelmed"

Q9: "What motivates you most?" (multi-select, pick up to 3)
   - Accountability and tracking
   - Words of encouragement
   - Data and insights about my progress
   - Structure and routine
   - Freedom to explore
   - Connection with others

Q10: "Anything else you'd like Ora to know about you?" (open-ended text)
   - Placeholder: "Share as much or as little as you'd like..."
   - Max 1000 characters
   - Optional skip button

WRITING GUIDELINES:
- Warm, conversational tone (not clinical)
- Use "you" language, not "the user"
- Questions should feel like a friendly conversation
- No guilt or judgment in any answer option
- Include a "prefer not to say" or skip option where appropriate
- Avoid jargon (no "CBT", "DBT" etc. in user-facing copy)
- Each question should have a brief subheading explaining why we're asking
- Progress indicator: "Question X of 10"

INTRO COPY:
Write a brief, warm intro that appears before the first question explaining:
- What the quiz is for (personalization)
- How long it takes (~2 minutes)
- That answers can be changed later
- That all responses are private

COMPLETION COPY:
Write copy for after the quiz:
- Thank the user
- Brief summary of what happens next
- Excitement about their journey

ACCEPTANCE CRITERIA:
- All 10 questions are thoughtful, empathetic, and well-written
- Answer options cover the range without being overwhelming (5-7 per question)
- Question flow feels natural (easy → deeper → easy ending)
- Personalization mapping is clear and actionable
- JSON schema is properly structured
- Copy is warm and non-judgmental throughout

WHEN COMPLETE, run these commands:
```bash
curl -X PATCH http://localhost:3001/api/tasks/ORA-053 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'
curl -X POST http://localhost:3001/api/activity -H "Content-Type: application/json" -d '{"project_id": 3, "task_id": "ORA-053", "agent_type": "content", "action": "completed", "details": "Intake quiz questions written - 10 questions with answer options, data schema, and personalization mapping"}'
```

START NOW.
