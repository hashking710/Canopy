import { useState } from "react";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

// The row-button counterpart to useSubmitState — for one-off actions inside a table
// (mark reported, acknowledge, remove) where there's no single form to attach
// pending/error state to, just whichever row's button was clicked. Tracks *which*
// row is mid-action (to disable only that row's button, not the whole table) and
// surfaces a failure instead of the click silently doing nothing, which is what
// happened before this existed — none of these call sites awaited or caught their
// own promise.
export function useRowAction<TId>() {
  const [pendingId, setPendingId] = useState<TId | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (id: TId, action: () => Promise<void>) => {
    setError(null);
    setPendingId(id);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPendingId(null);
    }
  };

  return { pendingId, error, run };
}
