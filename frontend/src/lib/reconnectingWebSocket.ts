// Every WebSocket consumer in this app (facility live updates, master live updates)
// used to open a socket once and never recover from it dropping — a server restart,
// a laptop sleeping, or a flaky Wi-Fi hop on the Pi would silently freeze the
// dashboard on stale data with no visible sign anything was wrong. This is the one
// place that reconnect behavior lives, so every caller gets it for free instead of
// each hand-rolling (or forgetting) its own.
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;

export interface ConnectionCallbacks<TMessage> {
  onMessage: (msg: TMessage) => void;
  // Fires on every open/close transition — lets a caller show a "reconnecting…"
  // indicator instead of just going quietly stale. Optional: most callers only
  // care about messages.
  onStatusChange?: (connected: boolean) => void;
}

export function connectWithReconnect<TMessage>(
  buildUrl: () => string,
  { onMessage, onStatusChange }: ConnectionCallbacks<TMessage>,
): () => void {
  let ws: WebSocket | null = null;
  let closedByCaller = false;
  let reconnectDelay = INITIAL_RECONNECT_DELAY_MS;
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

  function connect() {
    ws = new WebSocket(buildUrl());

    ws.onopen = () => {
      reconnectDelay = INITIAL_RECONNECT_DELAY_MS; // reset backoff once a connection actually succeeds
      onStatusChange?.(true);
    };

    ws.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data) as TMessage);
      } catch {
        // A malformed frame shouldn't take the whole connection down — drop it and
        // keep listening for the next one.
      }
    };

    ws.onclose = () => {
      onStatusChange?.(false);
      if (closedByCaller) return;
      reconnectTimer = setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY_MS);
    };

    // A connection error still fires close right after — explicitly closing here
    // just makes sure that happens promptly rather than waiting on the browser's
    // own timeout for a half-open socket.
    ws.onerror = () => {
      ws?.close();
    };
  }

  connect();

  return () => {
    closedByCaller = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    ws?.close();
  };
}
