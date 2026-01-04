import { relations } from "drizzle-orm/relations";
import {
  ledgerEvents,
  ledgerLegs,
  correctedLedgerEvents,
  correctedLedgerLegs,
  seedEvents,
  seedEventLegs,
  acquisitionLots,
  disposalLinks,
} from "./schema";

export const ledgerLegsRelations = relations(ledgerLegs, ({ one, many }) => ({
  ledgerEvent: one(ledgerEvents, {
    fields: [ledgerLegs.eventId],
    references: [ledgerEvents.id],
  }),
  acquisitionLots: many(acquisitionLots),
  disposalLinks: many(disposalLinks),
}));

export const ledgerEventsRelations = relations(ledgerEvents, ({ many }) => ({
  ledgerLegs: many(ledgerLegs),
}));

export const correctedLedgerLegsRelations = relations(
  correctedLedgerLegs,
  ({ one }) => ({
    correctedLedgerEvent: one(correctedLedgerEvents, {
      fields: [correctedLedgerLegs.eventId],
      references: [correctedLedgerEvents.id],
    }),
  }),
);

export const correctedLedgerEventsRelations = relations(
  correctedLedgerEvents,
  ({ many }) => ({
    correctedLedgerLegs: many(correctedLedgerLegs),
  }),
);

export const seedEventLegsRelations = relations(seedEventLegs, ({ one }) => ({
  seedEvent: one(seedEvents, {
    fields: [seedEventLegs.eventId],
    references: [seedEvents.id],
  }),
}));

export const seedEventsRelations = relations(seedEvents, ({ many }) => ({
  seedEventLegs: many(seedEventLegs),
}));

export const acquisitionLotsRelations = relations(
  acquisitionLots,
  ({ one, many }) => ({
    ledgerLeg: one(ledgerLegs, {
      fields: [acquisitionLots.acquiredLegId],
      references: [ledgerLegs.id],
    }),
    disposalLinks: many(disposalLinks),
  }),
);

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
