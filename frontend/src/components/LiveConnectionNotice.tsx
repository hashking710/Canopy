// Only renders anything when the live-update connection is actually down — absence
// of this banner is the normal state, so a working connection stays invisible rather
// than adding a permanent "Live" badge nobody needs to see. Without this, a dropped
// websocket used to fail silently: the page just stopped updating with no visible
// sign anything was wrong (see lib/reconnectingWebSocket.ts).
export function LiveConnectionNotice({ connected }: { connected: boolean }) {
  if (connected) return null;
  return (
    <div className="live-connection-notice" role="status">
      Live updates disconnected — reconnecting…
    </div>
  );
}
