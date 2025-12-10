import { relations } from "drizzle-orm";

import { acquisitionLots, disposalLinks, ledgerEvents, ledgerLegs, taxEvents } from "./schema";

export const ledgerLegsRelations = relations(ledgerLegs, ({ one, many }) => ({
  ledgerEvent: one(ledgerEvents, {
    fields: [ledgerLegs.eventId],
    references: [ledgerEvents.id],
  }),
  acquisitionLot: one(acquisitionLots, {
    fields: [ledgerLegs.id],
    references: [acquisitionLots.acquiredLegId],
  }),
  disposalLinks: many(disposalLinks),
}));

export const ledgerEventsRelations = relations(ledgerEvents, ({ many }) => ({
  ledgerLegs: many(ledgerLegs),
}));

export const acquisitionLotsRelations = relations(acquisitionLots, ({ one, many }) => ({
  ledgerLeg: one(ledgerLegs, {
    fields: [acquisitionLots.acquiredLegId],
    references: [ledgerLegs.id],
  }),
  disposalLinks: many(disposalLinks),
}));

export const disposalLinksRelations = relations(disposalLinks, ({ one }) => ({
  acquisitionLot: one(acquisitionLots, {
    fields: [disposalLinks.lotId],
    references: [acquisitionLots.id],
  }),
  ledgerLeg: one(ledgerLegs, {
    fields: [disposalLinks.disposalLegId],
    references: [ledgerLegs.id],
  }),
}));

export const taxEventsRelations = relations(taxEvents, ({ one }) => ({
  // Tax events attach to a disposal link or acquisition lot via source_id.
  // We keep it loose because both tables share the UUID domain.
  disposalLink: one(disposalLinks, {
    fields: [taxEvents.sourceId],
    references: [disposalLinks.id],
  }),
  acquisitionLot: one(acquisitionLots, {
    fields: [taxEvents.sourceId],
    references: [acquisitionLots.id],
  }),
}));
