"use client";

import { EventCard } from "@/components/EventCard";
import { SeedCorrectionItem } from "@/components/SeedCorrectionItem";
import { SpamCorrectionItem } from "@/components/SpamCorrectionItem";
import type { EventOrigin, LaneItemData } from "@/types/events";

type LaneItemProps = {
  item: LaneItemData;
  isSelected: boolean;
  isSpamMarkerChangePending: boolean;
  onToggleEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveSpamCorrection: (eventOrigin: EventOrigin) => void;
};

export function LaneItem({
  item,
  isSelected,
  isSpamMarkerChangePending,
  onToggleEventSelection,
  onRemoveSpamCorrection,
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
          selectionDisabled={isSpamMarkerChangePending}
          onSelectionChange={() => onToggleEventSelection(item.eventOrigin)}
        />
      );
    case "corrected-event":
      return (
        <EventCard
          id={item.id}
          timestamp={item.timestamp}
          eventOrigin={item.eventOrigin}
          legs={item.legs}
        />
      );
    case "seed-correction":
      return <SeedCorrectionItem timestamp={item.timestamp} legs={item.legs} />;
    case "spam-correction":
      return (
        <SpamCorrectionItem
          timestamp={item.timestamp}
          eventOrigin={item.eventOrigin}
          actionDisabled={isSpamMarkerChangePending}
          onRemove={() => onRemoveSpamCorrection(item.eventOrigin)}
        />
      );
  }
}
