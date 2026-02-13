"use client";

// Vibed and crappy, but for now this is enough

import { useMemo } from "react";
import { ListGroup } from "react-bootstrap";

import { useVisibleDay } from "@/contexts/VisibleDayContext";
import { hashForDay } from "@/lib/dayHash";

type DateEntry = { key: string; count: number };

type DateChooserProps = {
  dates: Record<string, number>;
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

function buildHierarchy(dates: Record<string, number>): YearNode[] {
  const years: YearNode[] = [];
  const yearsByKey = new Map<
    string,
    { year: YearNode; monthsByKey: Map<string, MonthNode> }
  >();

  for (const [key, count] of Object.entries(dates)) {
    const yearKey = key.slice(0, 4);
    const monthKey = key.slice(0, 7);

    let yearEntry = yearsByKey.get(yearKey);
    if (!yearEntry) {
      const yearNode: YearNode = {
        key: yearKey,
        count: 0,
        topDayKey: key,
        months: [],
      };
      yearEntry = { year: yearNode, monthsByKey: new Map() };
      yearsByKey.set(yearKey, yearEntry);
      years.push(yearNode);
    }

    let monthNode = yearEntry.monthsByKey.get(monthKey);
    if (!monthNode) {
      monthNode = { key: monthKey, count: 0, topDayKey: key, days: [] };
      yearEntry.monthsByKey.set(monthKey, monthNode);
      yearEntry.year.months.push(monthNode);
    }

    monthNode.days.push({ key, count });
    monthNode.count += count;
    yearEntry.year.count += count;
  }

  return years;
}

export function DateChooser({ dates }: DateChooserProps) {
  const { activeDayKey, setActiveDayKey } = useVisibleDay();

  const years = useMemo(() => buildHierarchy(dates), [dates]);
  const activeDay =
    activeDayKey && Object.prototype.hasOwnProperty.call(dates, activeDayKey)
      ? activeDayKey
      : null;
  const openYearKey = activeDay ? activeDay.slice(0, 4) : null;
  const openMonthKey = activeDay ? activeDay.slice(0, 7) : null;

  return (
    <>
      <h2 className="h6 text-uppercase text-muted mb-3">Jump to date</h2>
      <ListGroup>
        {years.map((year) => {
          const isYearOpen = openYearKey === year.key;

          return (
            <div key={year.key}>
              <ListGroup.Item
                action
                href={hashForDay(year.topDayKey)}
                onClick={(e) => {
                  e.preventDefault();
                  setActiveDayKey(year.topDayKey, "chooser");
                }}
                className="d-flex align-items-center justify-content-between"
              >
                <span>{year.key}</span>
                <span className="text-muted small">{year.count} events</span>
              </ListGroup.Item>

              {isYearOpen && (
                <ListGroup className="ms-3 mt-2">
                  {year.months.map((month) => {
                    const isMonthOpen = openMonthKey === month.key;

                    return (
                      <div key={month.key}>
                        <ListGroup.Item
                          action
                          href={hashForDay(month.topDayKey)}
                          onClick={(e) => {
                            e.preventDefault();
                            setActiveDayKey(month.topDayKey, "chooser");
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
                                active={activeDay === day.key}
                                onClick={(e) => {
                                  e.preventDefault();
                                  setActiveDayKey(day.key, "chooser");
                                }}
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
