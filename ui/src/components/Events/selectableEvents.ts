import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  CorrectedEventCardData,
  EventsByTimestamp,
  LedgerEvent,
  LaneItemData,
  RawEventCardData,
} from "@/types/events";

type SelectableEventItem = RawEventCardData | CorrectedEventCardData;

export const isSelectableEventItem = (
  item: LaneItemData,
): item is SelectableEventItem =>
  item.kind === "raw-event" ||
  (item.kind === "corrected-event" && item.eventOrigin.location !== "INTERNAL");

export const collectSelectableEventOriginKeys = (
  eventsByTimestamp: EventsByTimestamp,
): ReadonlySet<string> => {
  const selectableEventOriginKeys = new Set<string>();

  for (const columnsByTimestamp of Object.values(eventsByTimestamp)) {
    for (const columnItems of Object.values(columnsByTimestamp)) {
      for (const item of columnItems) {
        if (!isSelectableEventItem(item)) {
          continue;
        }

        const originKey = eventOriginKey(item.eventOrigin);
        selectableEventOriginKeys.add(originKey);
      }
    }
  }

  return selectableEventOriginKeys;
};

export const getSelectedEvents = (
  eventsByTimestamp: EventsByTimestamp,
  selectedEventOriginKeys: ReadonlySet<string>,
): readonly LedgerEvent[] => {
  const pendingSelectedEventOriginKeys = new Set(selectedEventOriginKeys);
  const selectedEvents: LedgerEvent[] = [];

  for (const columnsByTimestamp of Object.values(eventsByTimestamp)) {
    for (const columnItems of Object.values(columnsByTimestamp)) {
      for (const item of columnItems) {
        if (!isSelectableEventItem(item)) {
          continue;
        }

        const originKey = eventOriginKey(item.eventOrigin);
        if (!pendingSelectedEventOriginKeys.has(originKey)) {
          continue;
        }

        selectedEvents.push(item);
        pendingSelectedEventOriginKeys.delete(originKey);

        if (pendingSelectedEventOriginKeys.size === 0) {
          return selectedEvents;
        }
      }
    }
  }

  return selectedEvents;
};
