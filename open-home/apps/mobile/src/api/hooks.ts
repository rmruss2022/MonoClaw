import { useCallback, useEffect, useRef, useState } from "react";
import { api, AuthError } from "@/api/client";
import { useAuth } from "@/context/AuthContext";

interface PollState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refresh: () => void;
}

/**
 * Poll a hub GET endpoint on an interval. Bounces to login on 401.
 * Pass intervalMs = 0 to fetch once (no polling).
 */
export function usePoll<T = any>(path: string, intervalMs = 5000): PollState<T> {
  const { expire } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);

  const tick = useCallback(async () => {
    try {
      const d = await api<T>(path);
      if (!alive.current) return;
      setData(d);
      setError(null);
    } catch (e) {
      if (e instanceof AuthError) {
        expire();
        return;
      }
      if (alive.current) setError((e as Error).message);
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [path, expire]);

  useEffect(() => {
    alive.current = true;
    tick();
    if (intervalMs > 0) {
      const id = setInterval(tick, intervalMs);
      return () => {
        alive.current = false;
        clearInterval(id);
      };
    }
    return () => {
      alive.current = false;
    };
  }, [tick, intervalMs]);

  return { data, error, loading, refresh: tick };
}

/** Fire a POST command, returning the parsed response (and surfacing auth expiry). */
export function useCommand() {
  const { expire } = useAuth();
  return useCallback(
    async <T = any>(path: string, body: unknown): Promise<T | null> => {
      try {
        return await api<T>(path, { method: "POST", body });
      } catch (e) {
        if (e instanceof AuthError) expire();
        return null;
      }
    },
    [expire]
  );
}
