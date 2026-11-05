/**
 * Life OS store — React context + reducer with AsyncStorage persistence.
 *
 * Wrap the Life OS navigation stack in <LifeOSProvider>. Screens read state and
 * dispatch actions via the useLifeOS() hook.
 */
import React, {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useMemo,
  useCallback,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LifeOSState, Journey, Milestone, RoadmapCycle, Topic } from './types';
import { buildSeedState, uid } from './seed';

const STORAGE_KEY = 'ora.lifeos.v1';

type Action =
  | { type: 'hydrate'; state: LifeOSState }
  | { type: 'addJourney'; pillarId: string; title: string; emoji: string; goal: string }
  | { type: 'deleteJourney'; journeyId: string }
  | { type: 'addTopic'; journeyId: string; label: string }
  | { type: 'toggleTopic'; journeyId: string; topicId: string }
  | { type: 'buildRoadmap'; journeyId: string }
  | { type: 'toggleMilestone'; journeyId: string; milestoneId: string }
  | { type: 'noteMilestone'; journeyId: string; milestoneId: string; note: string }
  | { type: 'closeCycle'; journeyId: string; reflection: string }
  | { type: 'revamp'; journeyId: string };

const activeCycle = (j: Journey): RoadmapCycle | undefined =>
  j.cycles.find((c) => c.id === j.activeCycleId);

/** Apply fn to the journey with id, returning a new state. */
const mapJourney = (
  state: LifeOSState,
  journeyId: string,
  fn: (j: Journey) => Journey
): LifeOSState => ({
  ...state,
  pillars: state.pillars.map((p) => ({
    ...p,
    journeys: p.journeys.map((j) => (j.id === journeyId ? fn(j) : j)),
  })),
});

function reducer(state: LifeOSState, action: Action): LifeOSState {
  switch (action.type) {
    case 'hydrate':
      return action.state;

    case 'addJourney': {
      const journey: Journey = {
        id: uid('journey'),
        pillarId: action.pillarId,
        title: action.title,
        emoji: action.emoji || '✨',
        goal: action.goal,
        topics: [],
        cycles: [],
      };
      return {
        ...state,
        pillars: state.pillars.map((p) =>
          p.id === action.pillarId ? { ...p, journeys: [...p.journeys, journey] } : p
        ),
      };
    }

    case 'deleteJourney':
      return {
        ...state,
        pillars: state.pillars.map((p) => ({
          ...p,
          journeys: p.journeys.filter((j) => j.id !== action.journeyId || j.seeded),
        })),
      };

    case 'addTopic':
      return mapJourney(state, action.journeyId, (j) => ({
        ...j,
        topics: [
          ...j.topics,
          { id: uid('topic'), label: action.label, weight: 2, status: 'idle' } as Topic,
        ],
      }));

    case 'toggleTopic':
      return mapJourney(state, action.journeyId, (j) => ({
        ...j,
        topics: j.topics.map((t) =>
          t.id !== action.topicId
            ? t
            : { ...t, status: t.status === 'selected' ? 'idle' : t.status === 'idle' ? 'selected' : t.status }
        ),
      }));

    case 'buildRoadmap':
      return mapJourney(state, action.journeyId, (j) => {
        const picked = j.topics.filter((t) => t.status === 'selected');
        if (picked.length === 0) return j;
        const milestones: Milestone[] = picked.map((t) => ({
          id: uid('ms'),
          topicId: t.id,
          title: t.label,
          done: false,
        }));
        const cycle: RoadmapCycle = {
          id: uid('cycle'),
          number: j.cycles.length + 1,
          createdAt: new Date().toISOString(),
          status: 'active',
          milestones,
        };
        return {
          ...j,
          topics: j.topics.map((t) =>
            t.status === 'selected' ? { ...t, status: 'in_progress' } : t
          ),
          cycles: [...j.cycles, cycle],
          activeCycleId: cycle.id,
        };
      });

    case 'toggleMilestone':
      return mapJourney(state, action.journeyId, (j) => {
        const cycle = activeCycle(j);
        if (!cycle) return j;
        return {
          ...j,
          cycles: j.cycles.map((c) =>
            c.id !== cycle.id
              ? c
              : {
                  ...c,
                  milestones: c.milestones.map((m) =>
                    m.id === action.milestoneId ? { ...m, done: !m.done } : m
                  ),
                }
          ),
        };
      });

    case 'noteMilestone':
      return mapJourney(state, action.journeyId, (j) => {
        const cycle = activeCycle(j);
        if (!cycle) return j;
        return {
          ...j,
          cycles: j.cycles.map((c) =>
            c.id !== cycle.id
              ? c
              : {
                  ...c,
                  milestones: c.milestones.map((m) =>
                    m.id === action.milestoneId
                      ? { ...m, notes: [m.notes, action.note].filter(Boolean).join('\n') }
                      : m
                  ),
                }
          ),
        };
      });

    case 'closeCycle':
      return mapJourney(state, action.journeyId, (j) => {
        const cycle = activeCycle(j);
        if (!cycle) return j;
        const doneTopicIds = new Set(
          cycle.milestones.filter((m) => m.done).map((m) => m.topicId)
        );
        return {
          ...j,
          topics: j.topics.map((t) =>
            doneTopicIds.has(t.id) ? { ...t, status: 'done' } : t
          ),
          cycles: j.cycles.map((c) =>
            c.id === cycle.id
              ? { ...c, status: 'closed', closedAt: new Date().toISOString(), reflection: action.reflection }
              : c
          ),
          activeCycleId: undefined,
        };
      });

    case 'revamp':
      // Reset any lingering in_progress topics back to idle so a fresh cloud
      // pick can begin. Done topics stay done.
      return mapJourney(state, action.journeyId, (j) => ({
        ...j,
        activeCycleId: undefined,
        topics: j.topics.map((t) =>
          t.status === 'in_progress' ? { ...t, status: 'idle' } : t
        ),
      }));

    default:
      return state;
  }
}

interface LifeOSContextValue {
  state: LifeOSState;
  ready: boolean;
  getJourney: (id: string) => Journey | undefined;
  getActiveCycle: (j: Journey) => RoadmapCycle | undefined;
  dispatch: React.Dispatch<Action>;
}

const LifeOSContext = createContext<LifeOSContextValue | null>(null);

export const LifeOSProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, undefined, buildSeedState);
  const [ready, setReady] = React.useState(false);

  // Hydrate from storage on mount.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (alive && raw) {
          const parsed = JSON.parse(raw) as LifeOSState;
          if (parsed?.pillars) dispatch({ type: 'hydrate', state: parsed });
        }
      } catch (e) {
        // Corrupt / missing store — fall back to seed already in state.
        console.warn('Life OS hydrate failed', e);
      } finally {
        if (alive) setReady(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // Persist on every change once hydrated.
  useEffect(() => {
    if (!ready) return;
    AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(state)).catch((e) =>
      console.warn('Life OS persist failed', e)
    );
  }, [state, ready]);

  const getJourney = useCallback(
    (id: string) => {
      for (const p of state.pillars) {
        const j = p.journeys.find((jj) => jj.id === id);
        if (j) return j;
      }
      return undefined;
    },
    [state]
  );

  const value = useMemo<LifeOSContextValue>(
    () => ({ state, ready, dispatch, getJourney, getActiveCycle: activeCycle }),
    [state, ready, getJourney]
  );

  return <LifeOSContext.Provider value={value}>{children}</LifeOSContext.Provider>;
};

export const useLifeOS = (): LifeOSContextValue => {
  const ctx = useContext(LifeOSContext);
  if (!ctx) throw new Error('useLifeOS must be used within <LifeOSProvider>');
  return ctx;
};
