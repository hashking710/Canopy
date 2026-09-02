import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatGrid } from "./StatGrid";
import type { Metric } from "../types";

function metric(overrides: Partial<Metric>): Metric {
  return { key: "temp_f", label: "temp", unit: "°F", value: 85.5, decimals: 1, ...overrides };
}

describe("StatGrid", () => {
  it("renders nothing for an empty stat list", () => {
    const { container } = render(<StatGrid stats={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("formats values to the configured decimal places", () => {
    render(<StatGrid stats={[metric({ value: 85, decimals: 1 }), metric({ key: "co2_ppm", value: 436, decimals: 0 })]} />);
    expect(screen.getByText("85.0")).toBeInTheDocument();
    expect(screen.getByText("436")).toBeInTheDocument();
  });

  it("appends the unit to the label, not the value", () => {
    render(<StatGrid stats={[metric({ label: "temp", unit: "°F", value: 85.5 })]} />);
    expect(screen.getByText("85.5")).toBeInTheDocument();
    expect(screen.getByText("temp °F")).toBeInTheDocument();
  });

  it("omits the unit suffix entirely when unit is empty", () => {
    render(<StatGrid stats={[metric({ label: "press psi", unit: "", value: 1345, decimals: 0 })]} />);
    expect(screen.getByText("press psi")).toBeInTheDocument();
  });

  // The column count is chosen to keep every row balanced (2+ items) rather than
  // a fixed count that can orphan a lone cell on its own row — e.g. a naive fixed
  // 3-column grid renders 4 stats as a row of 3 then a single leftover cell.
  it.each([
    [1, 1],
    [2, 2],
    [3, 3],
    [4, 2], // 2x2, not 3+1
    [5, 3], // 3+2, not a 5-wide single row
    [6, 3], // 3+3
    [7, 4], // 4+3, not 3+3+1
  ])("uses %i column(s) for %i stat(s)", (count, expectedColumns) => {
    const stats = Array.from({ length: count }, (_, i) => metric({ key: `metric-${i}` }));
    const { container } = render(<StatGrid stats={stats} />);
    const grid = container.querySelector(".stat-grid") as HTMLElement;
    expect(grid.style.gridTemplateColumns).toBe(`repeat(${expectedColumns}, minmax(0, 1fr))`);
  });
});
