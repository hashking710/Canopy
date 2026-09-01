import { Component, type ErrorInfo, type ReactNode } from "react";
import { Card } from "./Card";

// React error boundaries must be class components — there is still no hook
// equivalent for getDerivedStateFromError/componentDidCatch as of React 19.
// Before this existed, one bad render anywhere (a malformed sensor reading, a
// chart computation on unexpected data) took down the *entire* dashboard to a
// blank white screen — including the nav and theme toggle, which live outside
// any single page's own render tree once React unmounts everything above the
// point that threw. Scoped per-route (see App.tsx, which remounts this on every
// route change via a `key`), so a crash on one page doesn't require a hard
// reload to recover — navigating elsewhere gets a fresh boundary.
interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Not wired to canopy_agent's report_system_error (server-side background/
    // request failures) — that would need a new endpoint to receive client-side
    // reports, a real but separate piece of scope. console.error is at least
    // real, inspectable signal for now, same as every uncaught exception
    // already was before this boundary existed.
    console.error("Canopy dashboard crashed rendering this page:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="page">
          <Card>
            <p className="card-subtitle">Something went wrong on this page.</p>
            <p className="stat-label" style={{ margin: "8px 0 16px" }}>
              {this.state.error.message || "An unexpected error occurred while rendering this page."}
            </p>
            <a className="inline-button" href="/">
              Back to facility overview
            </a>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
