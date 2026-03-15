import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  CorrectedEventCardData,
  EventOrigin,
  EventsByTimestamp,
  LaneItemData,
  RawEventCardData,
} from "@/types/events";

type SelectableEventData = {
  selectableEventOrigins: readonly EventOrigin[];
  selectableEventOriginKeys: ReadonlySet<string>;
};

const isSelectableEvent = (
  item: LaneItemData,
): item is RawEventCardData | CorrectedEventCardData =>
  item.kind === "raw-event" || item.kind === "corrected-event";

export const collectSelectableEventOrigins = (
  eventsByTimestamp: EventsByTimestamp,
): SelectableEventData => {
  const selectableEventOrigins: EventOrigin[] = [];
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
        if (selectableEventOriginKeys.has(originKey)) {
          continue;
        }

        selectableEventOriginKeys.add(originKey);
        selectableEventOrigins.push(item.eventOrigin);
      }
    }
  }

  return { selectableEventOrigins, selectableEventOriginKeys };
};
