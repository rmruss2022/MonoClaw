/**
 * The agent that runs the home.
 *
 * This is the seam where open-home stays local-first: the model provider is
 * pluggable. Default is a local LLM (Ollama); set OPEN_HOME_MODEL to a cloud
 * model only if the user opts in. Tools are the home's controls — kept minimal
 * and policy-gated so the agent can *operate* the house without being a
 * single point of failure for anything safety-critical (see ARCHITECTURE.md).
 */
import type { EventBus, HomeEvent } from "./bus.ts";

export class Agent {
  readonly modelLabel: string;
  private bus: EventBus;

  constructor(bus: EventBus) {
    this.bus = bus;
    // local-first default; cloud is explicit opt-in via env.
    this.modelLabel = process.env.OPEN_HOME_MODEL ?? "ollama:llama3.1 (local)";
    this.bus.subscribe((e) => this.onEvent(e));
  }

  private onEvent(event: HomeEvent): void {
    // Phase 1: react to device events, run rules, answer questions.
    // For now, just observe. Real tool-calling loop lands with the MQTT bus.
    if (event.type !== "hub.heartbeat") {
      // eslint-disable-next-line no-console
      console.log(`[agent] observed ${event.type}`);
    }
  }

  /** Placeholder for the tool-calling query loop ("who was at the door at 2pm?"). */
  async ask(_question: string): Promise<string> {
    return "agent query loop not implemented yet — see ROADMAP Phase 1";
  }
}
