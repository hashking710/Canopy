// Some adapters read credentials from environment variables on the edge-agent server
// instead of (or in addition to) per-room adapter_config, since a single API key/token
// is usually shared across every room using that adapter. Nothing in adapter_config
// hints at that — without this, filling out the form and saving looks complete, but
// the room silently never reads data until someone finds the right doc and sets a
// server env var outside the app entirely.
export function EnvVarNotice({ envVars }: { envVars: Record<string, string> }) {
  const keys = Object.keys(envVars);
  if (keys.length === 0) return null;

  return (
    <div className="env-requirement-note">
      <div className="env-requirement-title">Also requires server configuration</div>
      <div>
        This adapter reads credentials from environment variables set on the edge-agent
        server (shared by every room using it) — adapter config above isn't enough on its
        own:
      </div>
      <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
        {keys.map((key) => (
          <li key={key}>
            <code>{key}</code> — {envVars[key]}
          </li>
        ))}
      </ul>
    </div>
  );
}
