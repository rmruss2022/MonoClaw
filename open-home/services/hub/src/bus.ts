/**
 * In-memory event bus stand-in. Phase 1 replaces the transport with MQTT
 * (device-gateway publishes, hub subscribes) but keeps this interface.
 */
export interface HomeEvent {
  type: string;
  ts: number;
  payload?: unknown;
}

type Handler = (event: HomeEvent) => void;

export class EventBus {
  private handlers = new Set<Handler>();
  private ring: HomeEvent[] = [];
  private readonly max = 200;

  publish(event: HomeEvent): void {
    this.ring.push(event);
    if (this.ring.length > this.max) this.ring.shift();
    for (const h of this.handlers) h(event);
  }

  subscribe(handler: Handler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  recent(): HomeEvent[] {
    return [...this.ring].reverse();
  }
}
