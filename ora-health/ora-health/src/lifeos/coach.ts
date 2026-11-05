/**
 * Coach — turns a Journey + its active roadmap into an agent-guided practice
 * session. Wraps the existing chat backend with Life-OS context. If the backend
 * is unreachable, falls back to a local scripted coach so practice still works
 * offline (and in demos / App Store review with no server).
 */
import { chatAPI, ChatMessage } from '../services/api';
import { Journey, Milestone } from './types';

export interface CoachContext {
  journeyTitle: string;
  goal: string;
  focus: string[]; // milestone titles being worked
}

const framing = (ctx: CoachContext): string =>
  [
    `You are Ora, a warm, focused practice coach inside a wellness app.`,
    `The user is on a "${ctx.journeyTitle}" journey. Their goal: ${ctx.goal}.`,
    `This session focuses on: ${ctx.focus.join(', ')}.`,
    `Coach them one small step at a time. Ask a grounding question, suggest a concrete`,
    `practice or reflection, and keep replies short and encouraging.`,
  ].join(' ');

export const openingLine = (ctx: CoachContext): string => {
  const first = ctx.focus[0] ?? 'your goal';
  return (
    `Let's work toward "${ctx.goal}". Today we're focusing on ${ctx.focus.length} ` +
    `thing${ctx.focus.length === 1 ? '' : 's'}: ${ctx.focus.join(', ')}.\n\n` +
    `Let's start with ${first}. Where are you with it right now — total beginner, ` +
    `rusty, or building momentum?`
  );
};

/** Local fallback if the network chat fails — keeps practice usable offline. */
const localCoach = (ctx: CoachContext, userText: string): string => {
  const focus = ctx.focus[0] ?? 'this';
  const lower = userText.toLowerCase();
  if (/beginner|new|never|start/.test(lower)) {
    return `Perfect place to start. For ${focus}, try 5 focused minutes today — small and repeatable beats a marathon. Want a specific first drill or reflection to do right now?`;
  }
  if (/stuck|hard|struggl|frustrat|overwhelm/.test(lower)) {
    return `That's worth slowing down for. Let's shrink ${focus} to one tiny piece you *can* do. What's the smallest version that still feels like progress?`;
  }
  if (/done|finished|got it|nailed|comfortable/.test(lower)) {
    return `Love that. Mark it complete on your roadmap when it feels solid. Ready to move to the next focus, or deepen ${focus} a little more?`;
  }
  return `Good. For ${focus}, here's a small next step: spend a few minutes on it today and notice one thing that felt easier than expected. What comes up when you try?`;
};

export const sendPractice = async (
  ctx: CoachContext,
  userText: string,
  history: ChatMessage[]
): Promise<ChatMessage> => {
  try {
    // Prepend framing as the first turn of history so the backend has context.
    const framed: ChatMessage[] = [
      { role: 'assistant', content: framing(ctx), timestamp: new Date().toISOString() },
      ...history,
    ];
    return await chatAPI.sendMessage(userText, framed);
  } catch {
    return {
      role: 'assistant',
      content: localCoach(ctx, userText),
      timestamp: new Date().toISOString(),
    };
  }
};
