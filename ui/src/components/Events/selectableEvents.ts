import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  CorrectedEventCardData,
  EventOrigin,
  EventsByTimestamp,
  LedgerLeg,
  LaneItemData,
  RawEventCardData,
} from "@/types/events";

export type SelectableEvent = {
  eventOrigin: EventOrigin;
  timestamp: string;
  legs: LedgerLeg[];
};

const isSelectableEventCard = (
  item: LaneItemData,
): item is RawEventCardData | CorrectedEventCardData =>
  (item.kind === "raw-event" || item.kind === "corrected-event") &&
  item.eventOrigin.location !== "INTERNAL";

export const selectableEventFromLaneItem = (
  item: LaneItemData,
): SelectableEvent | null => {
  if (!isSelectableEventCard(item)) {
    return null;
  }

  return {
    eventOrigin: item.eventOrigin,
    timestamp: item.timestamp,
    legs: item.legs,
  };
};

export const collectSelectableEvents = (
  eventsByTimestamp: EventsByTimestamp,
): ReadonlyMap<string, SelectableEvent> => {
  const selectableEventsByOriginKey = new Map<string, SelectableEvent>();

  for (const columnsByTimestamp of Object.values(eventsByTimestamp)) {
    for (const columnItems of Object.values(columnsByTimestamp)) {
      if (!columnItems) {
        continue;
      }

      for (const item of columnItems) {
        const selectableEvent = selectableEventFromLaneItem(item);
        if (!selectableEvent) {
          continue;
        }

        const originKey = eventOriginKey(selectableEvent.eventOrigin);
        if (selectableEventsByOriginKey.has(originKey)) {
          continue;
        }

        selectableEventsByOriginKey.set(originKey, selectableEvent);
      }
    }
  }

  return selectableEventsByOriginKey;
};
