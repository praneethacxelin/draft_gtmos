import { useEffect, useState, useCallback } from "react";
import { useStrategies } from "./useStrategies";

const KEY = "gtm.activeStrategyId";
const EVENT = "gtm.activeStrategyChanged";

export function useActiveStrategy() {
  const { data: strategies } = useStrategies();
  const [activeId, setActiveIdState] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(KEY);
  });

  // Sync state across hook instances
  useEffect(() => {
    function handleSync(e: Event) {
      const customEvent = e as CustomEvent<string | null>;
      if (customEvent.detail !== activeId) {
        setActiveIdState(customEvent.detail);
      }
    }
    window.addEventListener(EVENT, handleSync);
    return () => window.removeEventListener(EVENT, handleSync);
  }, [activeId]);

  // Default to first ready strategy if none chosen
  useEffect(() => {
    if (!strategies || activeId) return;
    const ready = strategies.find((s) => s.status === "ready") || strategies[0];
    if (ready) {
      setActiveIdState(ready.id);
      localStorage.setItem(KEY, ready.id);
      window.dispatchEvent(new CustomEvent(EVENT, { detail: ready.id }));
    }
  }, [strategies, activeId]);

  // If the chosen id is no longer in list, reset
  useEffect(() => {
    if (!strategies || !activeId) return;
    if (!strategies.find((s) => s.id === activeId)) {
      const fallback = strategies[0]?.id ?? null;
      setActiveIdState(fallback);
      if (fallback) {
        localStorage.setItem(KEY, fallback);
        window.dispatchEvent(new CustomEvent(EVENT, { detail: fallback }));
      } else {
        localStorage.removeItem(KEY);
        window.dispatchEvent(new CustomEvent(EVENT, { detail: null }));
      }
    }
  }, [strategies, activeId]);

  const setActiveId = useCallback((id: string | null) => {
    setActiveIdState(id);
    if (id) {
      localStorage.setItem(KEY, id);
      window.dispatchEvent(new CustomEvent(EVENT, { detail: id }));
    } else {
      localStorage.removeItem(KEY);
      window.dispatchEvent(new CustomEvent(EVENT, { detail: null }));
    }
  }, []);

  const active = strategies?.find((s) => s.id === activeId) ?? null;
  return { activeId, active, setActiveId, strategies: strategies ?? [] };
}
