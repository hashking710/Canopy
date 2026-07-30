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

  it("uses the 2-column layout for two or fewer stats", () => {
    const { container } = render(<StatGrid stats={[metric({}), metric({ key: "rh_pct" })]} />);
    expect(container.querySelector(".stat-grid")).toHaveClass("cols-2");
  });

  it("uses the default 3-column layout for more than two stats", () => {
    const { container } = render(
      <StatGrid stats={[metric({}), metric({ key: "rh_pct" }), metric({ key: "vpd_kpa" })]} />,
    );
    expect(container.querySelector(".stat-grid")).not.toHaveClass("cols-2");
  });
});
