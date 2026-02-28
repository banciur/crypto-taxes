"use client";

import { EventCard } from "@/components/EventCard";
import { SeedCorrectionItem } from "@/components/SeedCorrectionItem";
import { SpamCorrectionItem } from "@/components/SpamCorrectionItem";
import type { LaneItemData, SpamCorrectionItemData } from "@/types/events";

type LaneItemProps = {
  item: LaneItemData;
  isSelected: boolean;
  rawSelectionDisabled: boolean;
  onRawSelectionChange: (isSelected: boolean) => void;
  onRemoveSpamCorrection: (item: SpamCorrectionItemData) => void;
  spamActionDisabled: boolean;
  isRemovingSpamCorrection: boolean;
};

export function LaneItem({
  item,
  isSelected,
  rawSelectionDisabled,
  onRawSelectionChange,
  onRemoveSpamCorrection,
  spamActionDisabled,
  isRemovingSpamCorrection,
}: LaneItemProps) {
  switch (item.kind) {
    case "raw-event":
      return (
        <EventCard
          timestamp={item.timestamp}
          place={item.place}
          originId={item.originId}
          legs={item.legs}
          isSelected={isSelected}
          selectionDisabled={rawSelectionDisabled}
          onSelectionChange={onRawSelectionChange}
        />
      );
    case "corrected-event":
      return (
        <EventCard
          timestamp={item.timestamp}
          place={item.place}
          originId={item.originId}
          legs={item.legs}
        />
      );
    case "seed-correction":
      return <SeedCorrectionItem timestamp={item.timestamp} legs={item.legs} />;
    case "spam-correction":
      return (
        <SpamCorrectionItem
          timestamp={item.timestamp}
          place={item.place}
          eventOrigin={item.eventOrigin}
          isRemoving={isRemovingSpamCorrection}
          actionDisabled={spamActionDisabled}
          onRemove={() => onRemoveSpamCorrection(item)}
        />
      );
  }
}
