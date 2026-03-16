import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  CorrectedEventCardData,
  EventOrigin,
  EventsByTimestamp,
  LedgerLeg,
  LaneItemData,
  RawEventCardData,
} from "@/types/events";

type SelectableEventItem = RawEventCardData | CorrectedEventCardData;

export type SelectedSourceEvent = {
  eventOrigin: EventOrigin;
  timestamp: string;
  legs: LedgerLeg[];
};

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
      if (!columnItems) {
        continue;
      }

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

export const resolveSelectedSourceEvents = (
  eventsByTimestamp: EventsByTimestamp,
  selectedEventOriginKeys: ReadonlySet<string>,
): readonly SelectedSourceEvent[] => {
  const pendingSelectedEventOriginKeys = new Set(selectedEventOriginKeys);
  const selectedSourceEvents: SelectedSourceEvent[] = [];

  for (const columnsByTimestamp of Object.values(eventsByTimestamp)) {
    for (const columnItems of Object.values(columnsByTimestamp)) {
      if (!columnItems) {
        continue;
      }

      for (const item of columnItems) {
        if (!isSelectableEventItem(item)) {
          continue;
        }

        const originKey = eventOriginKey(item.eventOrigin);
        if (!pendingSelectedEventOriginKeys.has(originKey)) {
          continue;
        }

        selectedSourceEvents.push({
          eventOrigin: item.eventOrigin,
          timestamp: item.timestamp,
          legs: item.legs,
        });
        pendingSelectedEventOriginKeys.delete(originKey);

        if (pendingSelectedEventOriginKeys.size === 0) {
          return selectedSourceEvents;
        }
      }
    }
  }

  return selectedSourceEvents;
};
