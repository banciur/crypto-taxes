"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { ColumnKey } from "@/types/columns";

type UrlColumnSelectionContextType = {
  selected: Set<ColumnKey>;
  toggle: (key: ColumnKey) => void;
};

const parseColumnsParam = (value: string | null): Set<string> => {
  if (!value) {
    return new Set();
  }
  return new Set(
    value
      .split(",")
      .map((entry) => entry.trim())
      .filter((entry) => entry.length > 0),
  );
};

const UrlColumnSelectionContext = createContext<
  UrlColumnSelectionContextType | undefined
>(undefined);

export type UrlColumnSelectionConfig = {
  availableColumns: Set<ColumnKey>;
  defaultSelected: ColumnKey;
  paramName?: string;
};

export function UrlColumnSelectionProvider({
  config,
  children,
}: {
  config: UrlColumnSelectionConfig;
  children: ReactNode;
}) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const { availableColumns, defaultSelected, paramName = "columns" } = config;

  const selectedColumns = useMemo(() => {
    const rawColumns = parseColumnsParam(searchParams.get(paramName));
    const inter = availableColumns.intersection(rawColumns);
    if (inter.size == 0) {
      return new Set([defaultSelected]);
    }
    return inter;
  }, [availableColumns, defaultSelected, paramName, searchParams]);

  const updateUrl = (nextColumns: Set<ColumnKey>) => {
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.set(paramName, Array.from(nextColumns).join(","));
    router.replace(`${pathname}?${nextParams.toString()}`, { scroll: false });
  };

  const toggleColumn = (key: ColumnKey) => {
    if (!availableColumns.has(key)) return;
    const newSelection = new Set(selectedColumns);

    if (selectedColumns.has(key)) {
      newSelection.delete(key);
    } else {
      newSelection.add(key);
    }

    updateUrl(newSelection);
  };

  return (
    <UrlColumnSelectionContext.Provider
      value={{
        selected: selectedColumns,
        toggle: toggleColumn,
      }}
    >
      {children}
    </UrlColumnSelectionContext.Provider>
  );
}

export function useUrlColumnSelection(): UrlColumnSelectionContextType {
  const context = useContext(UrlColumnSelectionContext);
  if (!context) {
    throw new Error(
      "useUrlColumnSelection must be used within UrlColumnSelectionProvider",
    );
  }

  return context;
}
