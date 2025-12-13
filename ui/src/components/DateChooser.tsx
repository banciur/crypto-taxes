"use client";

// Vibed and doesn't have all the features but for now this is enough

import { useMemo, useState } from "react";
import { ListGroup } from "react-bootstrap";

type DateEntry = { key: string; count: number };

type DateChooserProps = {
  dates: DateEntry[];
};

type MonthNode = {
  key: string; // YYYY-MM
  count: number;
  topDayKey: string; // YYYY-MM-DD (latest in current ordering)
  days: DateEntry[];
};

type YearNode = {
  key: string; // YYYY
  count: number;
  topDayKey: string; // YYYY-MM-DD (latest in current ordering)
  months: MonthNode[];
};

function buildHierarchy(dates: DateEntry[]): YearNode[] {
  const years: YearNode[] = [];
  const yearsByKey = new Map<
    string,
    { year: YearNode; monthsByKey: Map<string, MonthNode> }
  >();

  for (const day of dates) {
    const yearKey = day.key.slice(0, 4);
    const monthKey = day.key.slice(0, 7);

    let yearEntry = yearsByKey.get(yearKey);
    if (!yearEntry) {
      const yearNode: YearNode = {
        key: yearKey,
        count: 0,
        topDayKey: day.key,
        months: [],
      };
      yearEntry = { year: yearNode, monthsByKey: new Map() };
      yearsByKey.set(yearKey, yearEntry);
      years.push(yearNode);
    }

    let monthNode = yearEntry.monthsByKey.get(monthKey);
    if (!monthNode) {
      monthNode = { key: monthKey, count: 0, topDayKey: day.key, days: [] };
      yearEntry.monthsByKey.set(monthKey, monthNode);
      yearEntry.year.months.push(monthNode);
    }

    monthNode.days.push(day);
    monthNode.count += day.count;
    yearEntry.year.count += day.count;
  }

  return years;
}

const hashForDay = (dayKey: string) => `#day-${dayKey}`;

export function DateChooser({ dates }: DateChooserProps) {
  const [openYear, setOpenYear] = useState<string | null>(null);
  const [openMonth, setOpenMonth] = useState<string | null>(null);

  const years = useMemo(() => buildHierarchy(dates), [dates]);

  return (
    <>
      <h2 className="h6 text-uppercase text-muted mb-3">Jump to date</h2>
      <ListGroup>
        {years.map((year) => {
          const isYearOpen = openYear === year.key;

          return (
            <div key={year.key}>
              <ListGroup.Item
                action
                href={hashForDay(year.topDayKey)}
                onClick={(e) => {
                  if (isYearOpen) {
                    e.preventDefault();
                    setOpenYear(null);
                    setOpenMonth(null);
                    return;
                  }
                  setOpenYear(year.key);
                  setOpenMonth(null);
                }}
                className="d-flex align-items-center justify-content-between"
              >
                <span>{year.key}</span>
                <span className="text-muted small">{year.count} events</span>
              </ListGroup.Item>

              {isYearOpen && (
                <ListGroup className="ms-3 mt-2">
                  {year.months.map((month) => {
                    const isMonthOpen = openMonth === month.key;

                    return (
                      <div key={month.key}>
                        <ListGroup.Item
                          action
                          href={hashForDay(month.topDayKey)}
                          onClick={(e) => {
                            if (isMonthOpen) {
                              e.preventDefault();
                              setOpenMonth(null);
                              return;
                            }
                            setOpenMonth(month.key);
                          }}
                          className="d-flex align-items-center justify-content-between"
                          style={{ fontSize: "0.875rem" }}
                        >
                          <span>{month.key}</span>
                          <span className="text-muted small">
                            {month.count} events
                          </span>
                        </ListGroup.Item>

                        {isMonthOpen ? (
                          <ListGroup className="ms-3 mt-2">
                            {month.days.map((day) => (
                              <ListGroup.Item
                                action
                                key={day.key}
                                href={hashForDay(day.key)}
                                className="d-flex align-items-center justify-content-between"
                                style={{ fontSize: "0.75rem" }}
                              >
                                <span>{day.key}</span>
                                <span className="text-muted">
                                  {day.count} events
                                </span>
                              </ListGroup.Item>
                            ))}
                          </ListGroup>
                        ) : null}
                      </div>
                    );
                  })}
                </ListGroup>
              )}
            </div>
          );
        })}
      </ListGroup>
    </>
  );
}
