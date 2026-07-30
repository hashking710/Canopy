import { describe, expect, it } from "vitest";
import { adapterConfigToValues, isListField, valuesToAdapterConfig } from "./adapterConfig";

const MODBUS_SCHEMA = {
  host: "TCP only: device IP/hostname",
  registers: "list of {metric, address, register_type, data_type, word_order, scale, offset}",
};

describe("isListField", () => {
  it("recognizes a 'list of ...' schema description", () => {
    expect(isListField("list of {metric, address}")).toBe(true);
  });

  it("treats a plain scalar description as not a list field", () => {
    expect(isListField("TCP only: device IP/hostname")).toBe(false);
  });
});

describe("adapterConfigToValues / valuesToAdapterConfig", () => {
  it("renders scalar config values as plain strings and round-trips them", () => {
    const config = { host: "192.168.1.50" };
    const values = adapterConfigToValues(config, MODBUS_SCHEMA);
    expect(values.host).toBe("192.168.1.50");
    expect(valuesToAdapterConfig(values, MODBUS_SCHEMA)).toEqual({ host: "192.168.1.50" });
  });

  it("renders a 'list of' field as pretty-printed JSON and round-trips it", () => {
    const config = { registers: [{ metric: "temp_f", address: 0, register_type: "holding" }] };
    const values = adapterConfigToValues(config, MODBUS_SCHEMA);
    expect(JSON.parse(values.registers)).toEqual(config.registers);
    expect(valuesToAdapterConfig(values, MODBUS_SCHEMA)).toEqual(config);
  });

  it("omits keys left blank rather than sending empty strings", () => {
    expect(valuesToAdapterConfig({ host: "", registers: "" }, MODBUS_SCHEMA)).toEqual({});
  });

  it("throws when a 'list of' field contains invalid JSON, for the caller to surface", () => {
    expect(() => valuesToAdapterConfig({ registers: "{not json" }, MODBUS_SCHEMA)).toThrow();
  });
});
