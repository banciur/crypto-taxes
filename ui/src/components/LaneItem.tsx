"use client";

import { EventCard } from "@/components/EventCard";
import { LedgerCorrectionItem } from "@/components/LedgerCorrectionItem";
import type { EventOrigin, LaneItemData } from "@/types/events";

type LaneItemProps = {
  item: LaneItemData;
  isSelectable: boolean;
  isSelected: boolean;
  isCorrectionChangePending: boolean;
  onToggleEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveCorrection: (correctionId: string) => void;
};

export function LaneItem({
  item,
  isSelectable,
  isSelected,
  isCorrectionChangePending,
  onToggleEventSelection,
  onRemoveCorrection,
}: LaneItemProps) {
  switch (item.kind) {
    case "raw-event":
    case "corrected-event":
      return (
        <EventCard
          event={item}
          isSelected={isSelected}
          selectionDisabled={isSelectable && isCorrectionChangePending}
          onSelectionChange={
            isSelectable
              ? () => onToggleEventSelection(item.eventOrigin)
              : undefined
          }
        />
      );
    case "correction":
      return (
        <LedgerCorrectionItem
          item={item}
          actionDisabled={isCorrectionChangePending}
          onRemove={() => onRemoveCorrection(item.id)}
        />
      );
  }
}
