"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { resolveSelectedColumns } from "@/lib/columnSelection";
import { AVAILABLE_COLUMNS, ColumnKey, COLUMNS_PARAM_NAME } from "@/consts";

type UrlColumnSelectionContextType = {
  selected: Set<ColumnKey>;
  toggle: (key: ColumnKey) => void;
};

const UrlColumnSelectionContext = createContext<
  UrlColumnSelectionContextType | undefined
>(undefined);

export function UrlColumnSelectionProvider({
  children,
}: {
  children: ReactNode;
}) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const selectedColumns = useMemo(
    () => resolveSelectedColumns(searchParams.get(COLUMNS_PARAM_NAME)),
    [searchParams],
  );

  const updateUrl = (nextColumns: Set<ColumnKey>) => {
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.set(COLUMNS_PARAM_NAME, Array.from(nextColumns).join(","));
    router.replace(`${pathname}?${nextParams.toString()}`, { scroll: false });
  };

  const toggleColumn = (key: ColumnKey) => {
    if (!AVAILABLE_COLUMNS.has(key)) return;
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
