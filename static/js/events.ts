/* Events - TypeScript */
interface AppEventListener {
  event: string;
  handler: (data: any) => void;
  once?: boolean;
}

class EventEmitter {
  private listeners: Map<string, AppEventListener[]> = new Map();

  on(event: string, handler: (data: any) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push({ event, handler });
  }

  once(event: string, handler: (data: any) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push({ event, handler, once: true });
  }

  emit(event: string, data?: any): void {
    const handlers = this.listeners.get(event) || [];
    handlers.forEach((h) => {
      h.handler(data);
      if (h.once) {
        this.off(event, h.handler);
      }
    });
  }

  off(event: string, handler: (data: any) => void): void {
    const handlers = this.listeners.get(event);
    if (handlers) {
      this.listeners.set(event, handlers.filter((h) => h.handler !== handler));
    }
  }
}

const events = new EventEmitter();
(window as any).events = events;
(window as any).EventEmitter = EventEmitter;