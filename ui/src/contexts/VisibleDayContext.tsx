"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { dayKeyFromHash, hashForDay } from "@/lib/dayHash";

type VisibleDaySource = "scroll" | "chooser" | "hash" | "init";

type VisibleDayContextType = {
  activeDayKey: string | null;
  activeDaySource: VisibleDaySource;
  setActiveDayKey: (dayKey: string | null, source: VisibleDaySource) => void;
};

type ActiveDayState = {
  key: string | null;
  source: VisibleDaySource;
};

const VisibleDayContext = createContext<VisibleDayContextType | undefined>(
  undefined,
);

export function VisibleDayProvider({ children }: { children: ReactNode }) {
  const [activeDay, setActiveDay] = useState<ActiveDayState>({
    key: null,
    source: "init",
  });

  const setActiveDayKey = useCallback(
    (dayKey: string | null, source: VisibleDaySource) => {
      setActiveDay((prev) => {
        if (prev.key === dayKey && prev.source === source) {
          return prev;
        }
        return { key: dayKey, source };
      });
    },
    [],
  );

  useEffect(() => {
    const handleHashChange = () => {
      const dayKey = dayKeyFromHash(window.location.hash);
      setActiveDayKey(dayKey, "hash");
    };

    handleHashChange();
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, [setActiveDayKey]);

  useEffect(() => {
    const currentHash = window.location.hash;

    if (!activeDay.key) {
      if (!dayKeyFromHash(currentHash)) return;
      const nextUrl = `${window.location.pathname}${window.location.search}`;
      history.replaceState(null, "", nextUrl);
      return;
    }

    const nextHash = hashForDay(activeDay.key);
    if (currentHash === nextHash) return;

    const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
    history.replaceState(null, "", nextUrl);
  }, [activeDay.key]);

  const value = useMemo(
    () => ({
      activeDayKey: activeDay.key,
      activeDaySource: activeDay.source,
      setActiveDayKey,
    }),
    [activeDay.key, activeDay.source, setActiveDayKey],
  );

  return (
    <VisibleDayContext.Provider value={value}>
      {children}
    </VisibleDayContext.Provider>
  );
}

export function useVisibleDay(): VisibleDayContextType {
  const context = useContext(VisibleDayContext);
  if (!context) {
    throw new Error("useVisibleDay must be used within VisibleDayProvider");
  }
  return context;
}
