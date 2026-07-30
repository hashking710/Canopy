import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectWithReconnect } from "./reconnectingWebSocket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    this.onclose?.();
  }

  triggerClose() {
    this.closed = true;
    this.onclose?.();
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("connectWithReconnect", () => {
  it("delivers parsed messages", () => {
    const onMessage = vi.fn();
    const disconnect = connectWithReconnect(() => "ws://test", { onMessage });

    MockWebSocket.instances[0].onmessage?.({ data: JSON.stringify({ type: "x" }) });

    expect(onMessage).toHaveBeenCalledWith({ type: "x" });
    disconnect();
  });

  it("ignores a malformed frame instead of crashing", () => {
    const onMessage = vi.fn();
    connectWithReconnect(() => "ws://test", { onMessage });

    expect(() => MockWebSocket.instances[0].onmessage?.({ data: "not json" })).not.toThrow();
    expect(onMessage).not.toHaveBeenCalled();
  });

  it("reconnects after the socket closes", () => {
    const onStatusChange = vi.fn();
    const disconnect = connectWithReconnect(() => "ws://test", { onMessage: vi.fn(), onStatusChange });

    expect(MockWebSocket.instances).toHaveLength(1);
    MockWebSocket.instances[0].triggerClose();
    expect(onStatusChange).toHaveBeenCalledWith(false);
    expect(MockWebSocket.instances).toHaveLength(1); // not yet — waits for the backoff delay

    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(2);

    disconnect();
  });

  it("backs off exponentially on repeated failures, doubling each time", () => {
    const disconnect = connectWithReconnect(() => "ws://test", { onMessage: vi.fn() });

    MockWebSocket.instances[0].triggerClose();
    vi.advanceTimersByTime(1000); // first retry at 1s
    expect(MockWebSocket.instances).toHaveLength(2);

    MockWebSocket.instances[1].triggerClose();
    vi.advanceTimersByTime(1999);
    expect(MockWebSocket.instances).toHaveLength(2); // not yet — second retry needs 2s
    vi.advanceTimersByTime(1);
    expect(MockWebSocket.instances).toHaveLength(3);

    disconnect();
  });

  it("resets the backoff delay back to 1s after a successful connection", () => {
    const disconnect = connectWithReconnect(() => "ws://test", { onMessage: vi.fn() });

    const first = MockWebSocket.instances[0];
    first.triggerClose();
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(2);

    // This reconnect succeeds (onopen fires) before dropping again — the next retry
    // should be back at the initial 1s delay, not the doubled 2s from last time.
    const second = MockWebSocket.instances[1];
    second.onopen?.();
    second.triggerClose();
    vi.advanceTimersByTime(999);
    expect(MockWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(MockWebSocket.instances).toHaveLength(3);

    disconnect();
  });

  it("stops reconnecting once the caller explicitly disconnects", () => {
    const disconnect = connectWithReconnect(() => "ws://test", { onMessage: vi.fn() });

    disconnect();
    expect(MockWebSocket.instances[0].closed).toBe(true);

    vi.advanceTimersByTime(60_000);
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("caps the reconnect delay at 30s", () => {
    const disconnect = connectWithReconnect(() => "ws://test", { onMessage: vi.fn() });

    // Fail repeatedly without ever succeeding: 1s, 2s, 4s, 8s, 16s, then capped at 30s.
    const delays = [1000, 2000, 4000, 8000, 16000, 30000, 30000];
    for (const delay of delays) {
      const before = MockWebSocket.instances.length;
      MockWebSocket.instances[before - 1].triggerClose();
      vi.advanceTimersByTime(delay - 1);
      expect(MockWebSocket.instances).toHaveLength(before);
      vi.advanceTimersByTime(1);
      expect(MockWebSocket.instances).toHaveLength(before + 1);
    }

    disconnect();
  });
});
