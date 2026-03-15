import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  CorrectedEventCardData,
  EventOrigin,
  EventsByTimestamp,
  LaneItemData,
  RawEventCardData,
} from "@/types/events";

const isSelectableEvent = (
  item: LaneItemData,
): item is RawEventCardData | CorrectedEventCardData =>
  item.kind === "raw-event" || item.kind === "corrected-event";

export const collectSelectableEvents = (
  eventsByTimestamp: EventsByTimestamp,
): ReadonlyMap<string, EventOrigin> => {
  const selectableEventsByOriginKey = new Map<string, EventOrigin>();

  for (const columnsByTimestamp of Object.values(eventsByTimestamp)) {
    for (const columnItems of Object.values(columnsByTimestamp)) {
      if (!columnItems) {
        continue;
      }

      for (const item of columnItems) {
        if (!isSelectableEvent(item)) {
          continue;
        }

        const originKey = eventOriginKey(item.eventOrigin);
        if (selectableEventsByOriginKey.has(originKey)) {
          continue;
        }

        selectableEventsByOriginKey.set(originKey, item.eventOrigin);
      }
    }
  }

  return selectableEventsByOriginKey;
};
