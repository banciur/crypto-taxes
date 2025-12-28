"use client";

import { Form } from "react-bootstrap";
import { COLUMN_NAMES, ColumnKey } from "@/consts";

type ColumnChooserProps = {
  selected: Set<ColumnKey>;
  minSelected?: number;
  maxSelected?: number;
  onToggle: (key: ColumnKey) => void;
  title?: string;
};

export function ColumnChooser({
  selected,
  minSelected = 1,
  maxSelected = 4,
  onToggle,
  title = "Columns",
}: ColumnChooserProps) {
  return (
    <Form className="mb-4">
      <div className="text-uppercase text-muted small mb-2">{title}</div>
      {Array.from(COLUMN_NAMES, ([columnKey, columnLabel]) => {
        const isSelected = selected.has(columnKey);
        const disableUncheck = isSelected && selected.size <= minSelected;
        const disableCheck = !isSelected && selected.size >= maxSelected;

        return (
          <Form.Check
            key={columnKey}
            type="checkbox"
            id={`column-toggle-${columnKey}`}
            label={columnLabel}
            checked={isSelected}
            onChange={() => onToggle(columnKey)}
            disabled={disableUncheck || disableCheck}
            className="mb-1"
            style={{ userSelect: "none" }}
          />
        );
      })}
    </Form>
  );
}
