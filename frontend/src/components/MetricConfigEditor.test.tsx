import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MetricConfigEditor } from "./MetricConfigEditor";
import { emptyMetricRow, metricConfigToRows, type MetricConfigRow } from "../lib/metricConfig";

describe("MetricConfigEditor", () => {
  it("shows an empty-state message with no rows", () => {
    render(<MetricConfigEditor rows={[]} onChange={vi.fn()} needsRange={false} />);
    expect(screen.getByText("no metrics configured yet")).toBeInTheDocument();
  });

  it("renders each row's fields pre-filled", () => {
    const rows = metricConfigToRows({ temp_f: { label: "temp", unit: "°F", min: 65, max: 85 } });
    render(<MetricConfigEditor rows={rows} onChange={vi.fn()} needsRange />);
    expect(screen.getByDisplayValue("temp_f")).toBeInTheDocument();
    expect(screen.getByDisplayValue("temp")).toBeInTheDocument();
    expect(screen.getByDisplayValue("°F")).toBeInTheDocument();
  });

  it("appends a blank row when '+ add metric' is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<MetricConfigEditor rows={[]} onChange={onChange} needsRange={false} />);

    await user.click(screen.getByText("+ add metric"));
    expect(onChange).toHaveBeenCalledWith([emptyMetricRow()]);
  });

  it("removes a row when its 'remove' button is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const rows = metricConfigToRows({
      temp_f: { label: "temp" },
      rh_pct: { label: "RH" },
    });
    render(<MetricConfigEditor rows={rows} onChange={onChange} needsRange={false} />);

    await user.click(screen.getAllByText("remove")[0]);
    expect(onChange).toHaveBeenCalledWith([rows[1]]);
  });

  it("checking 'derived' reports the row as derived via onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const row: MetricConfigRow = { ...emptyMetricRow(), key: "vpd_kpa", label: "VPD" };
    render(<MetricConfigEditor rows={[row]} onChange={onChange} needsRange />);

    expect(screen.getByPlaceholderText("min (required)")).toBeInTheDocument();
    await user.click(screen.getByText("derived"));
    expect(onChange).toHaveBeenCalledWith([{ ...row, derived: true }]);
  });

  it("hides min/max/step for a row that is already derived", () => {
    const row: MetricConfigRow = { ...emptyMetricRow(), key: "vpd_kpa", label: "VPD", derived: true };
    render(<MetricConfigEditor rows={[row]} onChange={vi.fn()} needsRange />);
    expect(screen.queryByPlaceholderText("min (required)")).not.toBeInTheDocument();
  });
});
