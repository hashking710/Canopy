import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useSubmitState } from "./useSubmitState";

describe("useSubmitState", () => {
  it("tracks submitting while the action is in flight, then clears it", async () => {
    const { result } = renderHook(() => useSubmitState());
    expect(result.current.submitting).toBe(false);

    let resolveAction: () => void = () => {};
    const action = () => new Promise<void>((resolve) => (resolveAction = resolve));

    act(() => {
      result.current.run(action);
    });
    await waitFor(() => expect(result.current.submitting).toBe(true));

    act(() => resolveAction());
    await waitFor(() => expect(result.current.submitting).toBe(false));
  });

  it("sets success to true after the action resolves, and clears it after the timeout", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useSubmitState());

    await act(async () => {
      await result.current.run(() => Promise.resolve());
    });
    expect(result.current.success).toBe(true);
    expect(result.current.error).toBe(null);

    act(() => vi.advanceTimersByTime(2500));
    expect(result.current.success).toBe(false);
    vi.useRealTimers();
  });

  it("sets error (not success) when the action rejects, using the error's message", async () => {
    const { result } = renderHook(() => useSubmitState());

    await act(async () => {
      await result.current.run(() => Promise.reject(new Error("weight exceeds source")));
    });

    expect(result.current.error).toBe("weight exceeds source");
    expect(result.current.success).toBe(false);
    expect(result.current.submitting).toBe(false);
  });

  it("clears a previous error and success state when a new run starts", async () => {
    const { result } = renderHook(() => useSubmitState());

    await act(async () => {
      await result.current.run(() => Promise.reject(new Error("first failure")));
    });
    expect(result.current.error).toBe("first failure");

    let resolveSecond: () => void = () => {};
    act(() => {
      result.current.run(() => new Promise<void>((resolve) => (resolveSecond = resolve)));
    });
    await waitFor(() => expect(result.current.error).toBe(null));

    act(() => resolveSecond());
  });
});
