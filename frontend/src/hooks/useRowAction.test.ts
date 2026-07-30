import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useRowAction } from "./useRowAction";

describe("useRowAction", () => {
  it("tracks which row id is pending, then clears it", async () => {
    const { result } = renderHook(() => useRowAction<number>());
    expect(result.current.pendingId).toBe(null);

    let resolveAction: () => void = () => {};
    const action = () => new Promise<void>((resolve) => (resolveAction = resolve));

    act(() => {
      result.current.run(42, action);
    });
    await waitFor(() => expect(result.current.pendingId).toBe(42));

    act(() => resolveAction());
    await waitFor(() => expect(result.current.pendingId).toBe(null));
  });

  it("surfaces an error when the action rejects, instead of failing silently", async () => {
    const { result } = renderHook(() => useRowAction<string>());

    await act(async () => {
      await result.current.run("rule-1", () => Promise.reject(new Error("network error")));
    });

    expect(result.current.error).toBe("network error");
    expect(result.current.pendingId).toBe(null);
  });

  it("clears a previous error when a new action starts", async () => {
    const { result } = renderHook(() => useRowAction<string>());

    await act(async () => {
      await result.current.run("a", () => Promise.reject(new Error("first failure")));
    });
    expect(result.current.error).toBe("first failure");

    let resolveSecond: () => void = () => {};
    act(() => {
      result.current.run("b", () => new Promise<void>((resolve) => (resolveSecond = resolve)));
    });
    await waitFor(() => expect(result.current.error).toBe(null));

    act(() => resolveSecond());
  });
});
