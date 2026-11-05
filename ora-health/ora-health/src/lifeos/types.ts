/**
 * Life OS — data model
 *
 * Life OS is the layer of Ora Health that "gets filled out": a set of Pillars
 * (major life areas), each holding Journeys. A Journey has a Topic Cloud you
 * pick from, a Roadmap built from those picks, agent-assisted Practice, and a
 * cycle you close out and start again (close → revamp → repeat).
 */

export type PillarKind = 'structured' | 'open';

export type TopicStatus = 'idle' | 'selected' | 'in_progress' | 'done';

export interface Topic {
  id: string;
  label: string;
  /** Relative weight 1-3 — drives bubble size in the cloud. */
  weight: number;
  status: TopicStatus;
  /** Optional short note the user or agent attaches. */
  note?: string;
}

export interface Milestone {
  id: string;
  /** The topic this milestone is built from (topic.id). */
  topicId: string;
  title: string;
  done: boolean;
  /** Reflections / agent notes accrued while working this milestone. */
  notes?: string;
}

export type CycleStatus = 'active' | 'closed';

export interface RoadmapCycle {
  id: string;
  /** 1-based cycle number for this journey. */
  number: number;
  createdAt: string;
  closedAt?: string;
  status: CycleStatus;
  milestones: Milestone[];
  /** Written when the cycle is closed out. */
  reflection?: string;
}

export interface Journey {
  id: string;
  pillarId: string;
  title: string;
  emoji: string;
  /** Where the user wants to get to. */
  goal: string;
  /** Seeded structured aspects can't be deleted; user journeys can. */
  seeded?: boolean;
  topics: Topic[];
  cycles: RoadmapCycle[];
  activeCycleId?: string;
}

export interface Pillar {
  id: string;
  name: string;
  emoji: string;
  kind: PillarKind;
  /** One of theme category colors. */
  color: string;
  blurb: string;
  journeys: Journey[];
}

export interface LifeOSState {
  version: number;
  pillars: Pillar[];
}
