import type { EventOrigin } from "@/types/events";

export const eventOriginKey = (eventOrigin: EventOrigin) =>
  `${eventOrigin.location}:${eventOrigin.externalId}`;
