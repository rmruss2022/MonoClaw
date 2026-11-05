/**
 * Seed content for Life OS.
 *
 * Family ships as a *structured* pillar: its aspects are pre-created journeys
 * that can't be deleted. Hobbies ships with Guitar as a worked example of an
 * *open* pillar journey. Everything else starts as an empty open pillar the
 * user fills in.
 */
import { LifeOSState, Journey, Topic } from './types';
import { theme } from '../theme';

let counter = 0;
export const uid = (prefix = 'id'): string =>
  `${prefix}_${Date.now().toString(36)}_${(counter++).toString(36)}`;

const topics = (labels: Array<[string, number]>): Topic[] =>
  labels.map(([label, weight]) => ({
    id: uid('topic'),
    label,
    weight,
    status: 'idle',
  }));

const seededJourney = (
  pillarId: string,
  title: string,
  emoji: string,
  goal: string,
  topicLabels: Array<[string, number]>
): Journey => ({
  id: uid('journey'),
  pillarId,
  title,
  emoji,
  goal,
  seeded: true,
  topics: topics(topicLabels),
  cycles: [],
});

const familyId = uid('pillar');
const hobbiesId = uid('pillar');
const careerId = uid('pillar');
const healthId = uid('pillar');
const relationshipsId = uid('pillar');
const growthId = uid('pillar');

const guitar: Journey = {
  id: uid('journey'),
  pillarId: hobbiesId,
  title: 'Guitar',
  emoji: '🎸',
  goal: 'Comfortably improvise and play songs I love',
  topics: topics([
    ['Triads', 3],
    ['Open chords', 3],
    ['Barre chords', 2],
    ['Alternate picking', 2],
    ['Licks & phrasing', 2],
    ['Music theory', 3],
    ['Strumming patterns', 2],
    ['Fingerpicking', 1],
    ['Ear training', 2],
    ['The CAGED system', 1],
    ['Scales & modes', 2],
    ['Rhythm & timing', 2],
  ]),
  cycles: [],
};

export const buildSeedState = (): LifeOSState => ({
  version: 1,
  pillars: [
    {
      id: familyId,
      name: 'Family',
      emoji: '🌳',
      kind: 'structured',
      color: theme.colors.categoryCoral,
      blurb: 'Where you came from — and how you carry it.',
      journeys: [
        seededJourney(familyId, 'Understanding My Parents', '👵', 'See my parents as whole people, with compassion', [
          ['Their life story', 3],
          ['Their wounds', 2],
          ['Patterns I inherited', 3],
          ['What they gave me', 2],
          ['What they couldn’t give', 2],
          ['Boundaries', 2],
          ['Forgiveness', 2],
          ['Gratitude', 1],
        ]),
        seededJourney(familyId, 'Grandparents & Lineage', '🕰️', 'Know my roots and the people I came from', [
          ['Their history', 2],
          ['Where we came from', 3],
          ['Traditions', 2],
          ['Migration & change', 1],
          ['Values passed down', 2],
          ['Stories & memory', 2],
        ]),
        seededJourney(familyId, 'How My Upbringing Shaped Me', '🪞', 'Understand the environment that formed me', [
          ['Household emotional climate', 3],
          ['Roles I played', 2],
          ['Rules I absorbed', 2],
          ['Coping strategies', 3],
          ['Beliefs about myself', 3],
          ['Beliefs about others', 2],
          ['What felt safe / unsafe', 2],
        ]),
        seededJourney(familyId, 'Inner Child Healing', '🧸', 'Reparent and comfort my younger self', [
          ['Meet the inner child', 3],
          ['Unmet needs', 3],
          ['Reparenting', 3],
          ['Safety & soothing', 2],
          ['Play & joy', 1],
          ['The age it froze', 2],
          ['Letters to younger me', 1],
        ]),
        seededJourney(familyId, 'Family Shadow Work', '🌑', 'Break cycles I don’t want to pass on', [
          ['Intergenerational patterns', 3],
          ['Family secrets', 2],
          ['The family myth', 2],
          ['Addiction / trauma lineage', 2],
          ['What goes unspoken', 2],
          ['Cycles to break', 3],
          ['New patterns to plant', 2],
        ]),
      ],
    },
    {
      id: hobbiesId,
      name: 'Hobbies',
      emoji: '🎨',
      kind: 'open',
      color: theme.colors.categoryGreen,
      blurb: 'The things you do for the love of doing them.',
      journeys: [guitar],
    },
    {
      id: careerId,
      name: 'Career',
      emoji: '💼',
      kind: 'open',
      color: theme.colors.categoryBlue,
      blurb: 'The work you’re building, seriously.',
      journeys: [],
    },
    {
      id: healthId,
      name: 'Health',
      emoji: '🌿',
      kind: 'open',
      color: theme.colors.categoryGreen,
      blurb: 'Body, energy, and the basics that hold everything up.',
      journeys: [],
    },
    {
      id: relationshipsId,
      name: 'Relationships',
      emoji: '💞',
      kind: 'open',
      color: theme.colors.categoryPurple,
      blurb: 'The people you choose and how you show up for them.',
      journeys: [],
    },
    {
      id: growthId,
      name: 'Inner Growth',
      emoji: '🌀',
      kind: 'open',
      color: theme.colors.categoryAmber,
      blurb: 'Who you’re becoming.',
      journeys: [],
    },
  ],
});
