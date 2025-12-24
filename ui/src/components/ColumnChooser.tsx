"use client";

import { Form } from "react-bootstrap";

import type { ColumnKey } from "@/types/columns";

export type ColumnOption = {
  key: ColumnKey;
  label: string;
};

type ColumnChooserProps = {
  columns: ColumnOption[];
  selected: Set<ColumnKey>;
  minSelected?: number;
  maxSelected?: number;
  onToggle: (key: ColumnKey) => void;
  title?: string;
};

export function ColumnChooser({
  columns,
  selected,
  minSelected = 1,
  maxSelected = 4,
  onToggle,
  title = "Columns",
}: ColumnChooserProps) {
  return (
    <Form className="mb-4">
      <div className="text-uppercase text-muted small mb-2">{title}</div>
      {columns.map((column) => {
        const isSelected = selected.has(column.key);
        const disableUncheck = isSelected && selected.size <= minSelected;
        const disableCheck = !isSelected && selected.size >= maxSelected;

        return (
          <Form.Check
            key={column.key}
            type="checkbox"
            id={`column-toggle-${column.key}`}
            label={column.label}
            checked={isSelected}
            onChange={() => onToggle(column.key)}
            disabled={disableUncheck || disableCheck}
            className="mb-1"
            style={{ userSelect: "none" }}
          />
        );
      })}
    </Form>
  );
}
