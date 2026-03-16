import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  CorrectedEventCardData,
  EventsByTimestamp,
  LaneItemData,
  RawEventCardData,
} from "@/types/events";

const isSelectableEvent = (
  item: LaneItemData,
): item is RawEventCardData | CorrectedEventCardData =>
  item.kind === "raw-event" || item.kind === "corrected-event";

export const collectSelectableEventOriginKeys = (
  eventsByTimestamp: EventsByTimestamp,
): ReadonlySet<string> => {
  const selectableEventOriginKeys = new Set<string>();

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
        selectableEventOriginKeys.add(originKey);
      }
    }
  }

  return selectableEventOriginKeys;
};
