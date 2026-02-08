# Manual Testing Instructions for Dynamic Behaviors

## Quick Test in Browser

1. **Open the app**: http://localhost:8081 (should already be logged in)

2. **Test each behavior by typing these messages**:

### Difficult Emotion Processing (Priority: 10)
```
I'm feeling really overwhelmed and can't cope with everything going on
```
**Look for**: Validating, empathetic response that doesn't jump to solutions

### Cognitive Reframing (Priority: 8)
```
I always fail at everything and nothing ever works out
```
**Look for**: Gentle questions that introduce nuance, counter-examples

### Weekly Planning (Priority: 7)
```
I want to plan my upcoming week and set intentions
```
**Look for**: Questions about priorities, 3-5 intentions, balance of work/self-care

### Weekly Review (Priority: 7)
```
How was my week? I want to reflect on what happened
```
**Look for**: Pattern recognition, wins celebration, learnings extraction

### Gratitude Practice (Priority: 6)
```
I'm so grateful for my supportive friends
```
**Look for**: Deeper exploration of "why", specificity, 3 gratitude items

### Goal Setting (Priority: 6)
```
I want to start exercising more regularly
```
**Look for**: SMART goal questions, breaking down to first step

### Values Clarification (Priority: 6)
```
What's really important to me in life? What do I value most?
```
**Look for**: Exploratory questions, pattern finding, current situation connection

### Energy Check-in (Priority: 5)
```
I'm feeling really tired and low energy today
```
**Look for**: Quick practical questions about sleep/food/movement, one action

### Free-form Chat (Priority: 1 - Fallback)
```
Just want to chat and share some thoughts with you
```
**Look for**: Warm, adaptive, following user's lead

## Check Backend Logs

After sending each message, check the backend logs for:
```
🎯 Activated behavior: [Behavior Name]
   Confidence: [0.00-1.00], Triggers: [matched triggers]
```

This will confirm which behavior was detected and activated for each message.

## What to Look For

1. **Correct Behavior Activation**: The right behavior should activate based on keywords
2. **System Prompt Application**: The response should match the behavior's tone and constraints
3. **Behavior Transitions**: Check database for logged transitions
4. **Priority Handling**: Higher priority behaviors (like Difficult Emotion Processing) should override lower ones when both match

## Database Check

To see behavior transitions:
```sql
SELECT * FROM behavior_transitions ORDER BY created_at DESC LIMIT 10;
```
