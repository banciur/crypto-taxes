"use client";

import { CorrectionItem } from "@/components/CorrectionItem";
import { CorrectionRemoveButton } from "@/components/CorrectionRemoveButton";
import { OriginIcon } from "@/components/OriginIcon";
import { OriginId } from "@/components/OriginId";
import type { SpamCorrectionItemData } from "@/types/events";

type SpamCorrectionItemProps = {
  item: SpamCorrectionItemData;
  actionDisabled: boolean;
  onRemove: () => void;
};

export function SpamCorrectionItem({
  item,
  actionDisabled,
  onRemove,
}: SpamCorrectionItemProps) {
  const { timestamp, eventOrigin } = item;
  const place = eventOrigin.location.toLowerCase();
  const action = (
    <CorrectionRemoveButton
      label={`Remove spam marker for ${eventOrigin.externalId}`}
      disabled={actionDisabled}
      onClick={onRemove}
    />
  );

  return (
    <CorrectionItem
      label="Spam marker"
      labelVariant="warning"
      timestamp={timestamp}
      action={action}
    >
      <div className="d-flex align-items-center gap-2">
        <span className="text-muted small">Origin</span>
        <OriginId
          originId={eventOrigin.externalId}
          place={place}
          className="small text-muted"
        />
        <OriginIcon place={place} className="ms-auto flex-shrink-0" />
      </div>
    </CorrectionItem>
  );
}
