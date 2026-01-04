"use client";

import { Form } from "react-bootstrap";
import { COLUMN_NAMES } from "@/consts";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";

const MAX_COLUMNS = 4;

type ColumnChooserProps = {
  minSelected?: number;
  maxSelected?: number;
  title?: string;
};

export function ColumnChooser({
  minSelected = 1,
  maxSelected = MAX_COLUMNS,
  title = "Columns",
}: ColumnChooserProps) {
  // TODO: as now events are generated on the backend here is only usage of context which is overkill
  const { selected, toggle } = useUrlColumnSelection();

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
            onChange={() => toggle(columnKey)}
            disabled={disableUncheck || disableCheck}
            className="mb-1"
            style={{ userSelect: "none" }}
          />
        );
      })}
    </Form>
  );
}
