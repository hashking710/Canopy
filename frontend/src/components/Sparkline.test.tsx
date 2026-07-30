import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sparkline } from "./Sparkline";

describe("Sparkline", () => {
  it("shows a placeholder message with fewer than 2 points", () => {
    const { container } = render(<Sparkline points={[{ ts: "2026-01-01T00:00:00Z", value: 1 }]} />);
    expect(container.textContent).toBe("not enough history yet");
    expect(container.querySelector("svg")).toBeNull();
  });

  it("renders an svg with a line for 2+ points", () => {
    const { container } = render(
      <Sparkline
        points={[
          { ts: "2026-01-01T00:00:00Z", value: 70 },
          { ts: "2026-01-01T00:01:00Z", value: 75 },
          { ts: "2026-01-01T00:02:00Z", value: 72 },
        ]}
      />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
    expect(polyline?.getAttribute("points")?.split(" ")).toHaveLength(3);
  });

  it("handles a flat line (all equal values) without dividing by zero", () => {
    const { container } = render(
      <Sparkline
        points={[
          { ts: "2026-01-01T00:00:00Z", value: 70 },
          { ts: "2026-01-01T00:01:00Z", value: 70 },
        ]}
      />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline?.getAttribute("points")).not.toContain("NaN");
  });
});
