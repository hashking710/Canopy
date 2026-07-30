import { useRef, useState } from "react";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

// Every quick-form in the compliance/plants/harvest area needs the same three things
// around its submit call — a disabled+labeled pending state, an error banner on
// failure, and *some* positive confirmation on success (previously there was none at
// all: a successful submit just silently reset the form, indistinguishable at a
// glance from nothing having happened). Centralized here since ~15 forms need this
// identical dance, not because any one of them is complex enough to deserve it alone.
export function useSubmitState() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const successTimeout = useRef<number | null>(null);

  const run = async (action: () => Promise<void>) => {
    setError(null);
    setSuccess(false);
    if (successTimeout.current) window.clearTimeout(successTimeout.current);
    setSubmitting(true);
    try {
      await action();
      setSuccess(true);
      successTimeout.current = window.setTimeout(() => setSuccess(false), 2500);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return { submitting, error, success, run };
}
