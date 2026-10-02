/**
 * AlphaBrain Universal Live SWR Hook
 * 
 * Implements Industry-Standard Triple-Tier Data Hydration:
 * 1. 0ms Instant Disk Hydration (localStorage) - Zero spinner on boot
 * 2. Background Revalidation (Network)
 * 3. Visibility & Focus Adaptive Polling (Pauses on screen-lock/app-switch, instant re-sync on foreground)
 * 4. Online/Offline Auto-Recovery (Fires instant re-sync on network reconnect)
 * 5. In-flight Request Deduplication Mutex (Prevents connection pool exhaustion)
 * 6. Deep Equality Mutation Guard (Zero unnecessary React DOM re-renders)
 */

import { useState, useEffect, useRef, useCallback } from 'react';

export interface UseLiveSWROptions<T> {
  key: string;
  fetcher: () => Promise<T>;
  refreshInterval?: number; // In milliseconds, defaults to 10,000 (10s)
  revalidateOnFocus?: boolean; // Defaults to true
  revalidateOnReconnect?: boolean; // Defaults to true
  initialData?: T;
  onSuccess?: (data: T) => void;
  onError?: (err: any) => void;
}

export interface UseLiveSWRReturn<T> {
  data: T;
  isLoading: boolean;
  isValidating: boolean;
  error: any | null;
  lastRefreshedAt: Date;
  mutate: (newData?: T | ((prev: T) => T), revalidate?: boolean) => Promise<void>;
  refresh: () => Promise<void>;
}

export function useLiveSWR<T>({
  key,
  fetcher,
  refreshInterval = 10000,
  revalidateOnFocus = true,
  revalidateOnReconnect = true,
  initialData,
  onSuccess,
  onError,
}: UseLiveSWROptions<T>): UseLiveSWRReturn<T> {
  // 1. Instant Synchronous Disk Hydration (0ms)
  const [data, setData] = useState<T>(() => {
    if (typeof window !== 'undefined') {
      try {
        const cached = localStorage.getItem(`swr:${key}`);
        if (cached) {
          return JSON.parse(cached);
        }
      } catch (e) {
        console.warn(`[LiveSWR] Disk hydration failed for ${key}:`, e);
      }
    }
    return initialData as T;
  });

  const [isLoading, setIsLoading] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      try {
        return !localStorage.getItem(`swr:${key}`) && initialData === undefined;
      } catch {
        return true;
      }
    }
    return true;
  });

  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [error, setError] = useState<any | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date>(new Date());

  // In-flight mutex to prevent duplicate overlapping network calls
  const inFlightRef = useRef<boolean>(false);
  const dataRef = useRef<T>(data);
  dataRef.current = data;

  const serializedRef = useRef<string>(data !== undefined ? JSON.stringify(data) : '');

  const lastFocusRevalidateRef = useRef<number>(0);
  const focusThrottleInterval = 5000; // 5-second focus throttle per Vercel/Linear standard

  // Revalidation Core
  const revalidate = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      return; // Skip when offline to save mobile radio battery
    }
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setIsValidating(true);

    try {
      const fresh = await fetcher();
      if (fresh !== undefined && fresh !== null) {
        const serialized = JSON.stringify(fresh);
        // Deep Equality Mutation Guard: Only update state if JSON hash mutated
        if (serialized !== serializedRef.current) {
          serializedRef.current = serialized;
          setData(fresh);
          dataRef.current = fresh;
          try {
            localStorage.setItem(`swr:${key}`, serialized);
          } catch (storageErr) {
            console.warn(`[LiveSWR] Disk cache write failed for ${key}:`, storageErr);
          }
        }
        setLastRefreshedAt(new Date());
        setError(null);
        if (onSuccess) onSuccess(fresh);
      }
    } catch (err) {
      console.warn(`[LiveSWR] Revalidation error for ${key}:`, err);
      setError(err);
      if (onError) onError(err);
    } finally {
      inFlightRef.current = false;
      setIsLoading(false);
      setIsValidating(false);
    }
  }, [key, fetcher, onSuccess, onError]);

  // Initial and Periodic Adaptive Polling
  useEffect(() => {
    // Initial fetch on mount
    revalidate();

    if (refreshInterval <= 0) return;

    let timer: NodeJS.Timeout | null = null;

    const startTimer = () => {
      if (timer) clearInterval(timer);
      timer = setInterval(() => {
        // Industry Standard: Pause polling if user minimized the app or screen is locked
        if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
          return;
        }
        revalidate();
      }, refreshInterval);
    };

    startTimer();

    // Visibility-change Listener (Screen unlock / App switch)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        const now = Date.now();
        if (now - lastFocusRevalidateRef.current > focusThrottleInterval) {
          lastFocusRevalidateRef.current = now;
          revalidate(); // Throttled instant re-sync on app foreground
        }
        startTimer();
      } else {
        if (timer) clearInterval(timer);
      }
    };

    // Window Focus Listener
    const handleFocus = () => {
      if (revalidateOnFocus) {
        const now = Date.now();
        if (now - lastFocusRevalidateRef.current > focusThrottleInterval) {
          lastFocusRevalidateRef.current = now;
          revalidate();
        }
      }
    };

    // Online Network Reconnection Listener
    const handleOnline = () => {
      if (revalidateOnReconnect) {
        revalidate();
      }
    };

    if (typeof window !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibilityChange);
      if (revalidateOnFocus) {
        window.addEventListener('focus', handleFocus);
      }
      if (revalidateOnReconnect) {
        window.addEventListener('online', handleOnline);
      }
    }

    return () => {
      if (timer) clearInterval(timer);
      if (typeof window !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibilityChange);
        if (revalidateOnFocus) {
          window.removeEventListener('focus', handleFocus);
        }
        if (revalidateOnReconnect) {
          window.removeEventListener('online', handleOnline);
        }
      }
    };
  }, [key, refreshInterval, revalidate, revalidateOnFocus, revalidateOnReconnect]);

  // Manual Mutation Function
  const mutate = useCallback(
    async (newData?: T | ((prev: T) => T), shouldRevalidate = true) => {
      if (newData !== undefined) {
        const resolved = typeof newData === 'function' ? (newData as (prev: T) => T)(dataRef.current) : newData;
        setData(resolved);
        dataRef.current = resolved;
        try {
          const serialized = JSON.stringify(resolved);
          serializedRef.current = serialized;
          localStorage.setItem(`swr:${key}`, serialized);
        } catch (e) {
          console.warn(`[LiveSWR] Mutate disk write failed for ${key}:`, e);
        }
      }
      if (shouldRevalidate) {
        await revalidate();
      }
    },
    [key, revalidate]
  );

  return {
    data,
    isLoading,
    isValidating,
    error,
    lastRefreshedAt,
    mutate,
    refresh: revalidate,
  };
}
