"use client";

import { EventCard } from "@/components/EventCard";
import { ReplacementCorrectionItem } from "@/components/ReplacementCorrectionItem";
import { SeedCorrectionItem } from "@/components/SeedCorrectionItem";
import { SpamCorrectionItem } from "@/components/SpamCorrectionItem";
import type { EventOrigin, LaneItemData } from "@/types/events";
import type { SelectableEvent } from "@/components/Events/selectableEvents";

type LaneItemProps = {
  item: LaneItemData;
  selectableEvent: SelectableEvent | null;
  isSelected: boolean;
  isCorrectionChangePending: boolean;
  onToggleEventSelection: (event: SelectableEvent) => void;
  onRemoveSpamCorrection: (eventOrigin: EventOrigin) => void;
  onRemoveReplacementCorrection: (correctionId: string) => void;
};

export function LaneItem({
  item,
  selectableEvent,
  isSelected,
  isCorrectionChangePending,
  onToggleEventSelection,
  onRemoveSpamCorrection,
  onRemoveReplacementCorrection,
}: LaneItemProps) {
  switch (item.kind) {
    case "raw-event":
      return (
        <EventCard
          id={item.id}
          timestamp={item.timestamp}
          eventOrigin={item.eventOrigin}
          legs={item.legs}
          isSelected={isSelected}
          selectionDisabled={
            selectableEvent === null || isCorrectionChangePending
          }
          onSelectionChange={
            selectableEvent === null
              ? undefined
              : () => onToggleEventSelection(selectableEvent)
          }
        />
      );
    case "corrected-event":
      return (
        <EventCard
          id={item.id}
          timestamp={item.timestamp}
          eventOrigin={item.eventOrigin}
          legs={item.legs}
          isSelected={isSelected}
          selectionDisabled={
            selectableEvent === null || isCorrectionChangePending
          }
          onSelectionChange={
            selectableEvent === null
              ? undefined
              : () => onToggleEventSelection(selectableEvent)
          }
        />
      );
    case "seed-correction":
      return <SeedCorrectionItem timestamp={item.timestamp} legs={item.legs} />;
    case "spam-correction":
      return (
        <SpamCorrectionItem
          timestamp={item.timestamp}
          eventOrigin={item.eventOrigin}
          actionDisabled={isCorrectionChangePending}
          onRemove={() => onRemoveSpamCorrection(item.eventOrigin)}
        />
      );
    case "replacement-correction":
      return (
        <ReplacementCorrectionItem
          correctionId={item.id}
          timestamp={item.timestamp}
          sources={item.sources}
          legs={item.legs}
          actionDisabled={isCorrectionChangePending}
          onRemove={() => onRemoveReplacementCorrection(item.id)}
        />
      );
  }
}
