import { describe, expect, it } from "vitest";
import { emptyMetricRow, metricConfigToRows, rowsToMetricConfig } from "./metricConfig";

describe("metricConfigToRows", () => {
  it("converts a metric_config object into editable rows", () => {
    const rows = metricConfigToRows({
      temp_f: { label: "temp", unit: "°F", decimals: 1, min: 65, max: 85, step: 0.5 },
    });
    expect(rows).toEqual([
      { key: "temp_f", label: "temp", unit: "°F", decimals: "1", min: "65", max: "85", step: "0.5", derived: false },
    ]);
  });

  it("marks a derived metric and leaves min/max/step blank", () => {
    const rows = metricConfigToRows({ vpd_kpa: { label: "VPD", unit: "kPa", derived: true } });
    expect(rows[0]).toMatchObject({ derived: true, min: "", max: "", step: "" });
  });
});

describe("rowsToMetricConfig", () => {
  it("round-trips through metricConfigToRows", () => {
    const original = { temp_f: { label: "temp", unit: "°F", decimals: 1, min: 65, max: 85, step: 0.5 } };
    expect(rowsToMetricConfig(metricConfigToRows(original))).toEqual(original);
  });

  it("omits min/max/step for a derived metric even if they were previously set", () => {
    const row = { ...emptyMetricRow(), key: "vpd_kpa", label: "VPD", derived: true, min: "1", max: "2", decimals: "" };
    const config = rowsToMetricConfig([row]);
    expect(config.vpd_kpa).toEqual({ label: "VPD", derived: true });
  });

  it("skips rows with no key (an in-progress or abandoned row)", () => {
    expect(rowsToMetricConfig([emptyMetricRow()])).toEqual({});
  });

  it("omits optional fields the user left blank rather than writing empty strings/NaN", () => {
    const row = { ...emptyMetricRow(), key: "co2_ppm", label: "CO2", decimals: "" };
    const config = rowsToMetricConfig([row]) as Record<string, Record<string, unknown>>;
    expect(config.co2_ppm).toEqual({ label: "CO2" });
  });
});
