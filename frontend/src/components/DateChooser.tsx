import { ListGroup } from "react-bootstrap";
import ListGroupItem from "react-bootstrap/ListGroupItem";

import { formatDateISO } from "@/lib/dateFormatter";

type DateChooserProps = {
  dates: { key: string; count: number }[];
};

export function DateChooser({ dates }: DateChooserProps) {
  return (
    <>
      <h2 className="h6 text-uppercase text-muted mb-3">Jump to date</h2>
      <ListGroup>
        {dates.map(({ key, count }) => {
          const label = formatDateISO(new Date(`${key}T00:00:00Z`));
          return (
            <ListGroupItem
              action
              href={`#day-${key}`}
              key={key}
              className="d-flex align-items-center justify-content-between"
            >
              <span>{label}</span>
              <span className="text-muted small">{count} events</span>
            </ListGroupItem>
          );
        })}
      </ListGroup>
    </>
  );
}
