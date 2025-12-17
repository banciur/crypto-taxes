import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const ledgerEvents = sqliteTable("ledger_events", {
  id: text().primaryKey().notNull(), // UUID stored as text
  timestamp: text().notNull(), // ISO-like DATETIME string
  ingestion: text().notNull(),
  eventType: text("event_type").notNull(),
  originLocation: text("origin_location").notNull(),
  originExternalId: text("origin_external_id").notNull(),
});

export const ledgerLegs = sqliteTable("ledger_legs", {
  id: text().primaryKey().notNull(), // UUID stored as text
  eventId: text("event_id")
    .notNull()
    .references(() => ledgerEvents.id),
  assetId: text("asset_id").notNull(),
  quantity: text().notNull(), // Decimal string
  walletId: text("wallet_id").notNull(),
  isFee: integer("is_fee", { mode: "boolean" }).notNull(),
});

export const correctedLedgerEvents = sqliteTable("corrected_ledger_events", {
  id: text().primaryKey().notNull(), // UUID stored as text
  timestamp: text().notNull(), // ISO-like DATETIME string
  ingestion: text().notNull(),
  eventType: text("event_type").notNull(),
  originLocation: text("origin_location").notNull(),
  originExternalId: text("origin_external_id").notNull(),
});

export const correctedLedgerLegs = sqliteTable("corrected_ledger_legs", {
  id: text().primaryKey().notNull(),
  eventId: text("event_id")
    .notNull()
    .references(() => correctedLedgerEvents.id),
  assetId: text("asset_id").notNull(),
  quantity: text().notNull(), // Decimal string
  walletId: text("wallet_id").notNull(),
  isFee: integer("is_fee", { mode: "boolean" }).notNull(),
});

export const seedEvents = sqliteTable("seed_events", {
  id: text().primaryKey().notNull(), // UUID stored as text
  timestamp: text().notNull(), // ISO-like DATETIME string
  pricePerToken: text("price_per_token").notNull(),
});

export const seedEventLegs = sqliteTable("seed_event_legs", {
  id: text().primaryKey().notNull(),
  eventId: text("event_id")
    .notNull()
    .references(() => seedEvents.id),
  assetId: text("asset_id").notNull(),
  quantity: text().notNull(),
  walletId: text("wallet_id").notNull(),
  isFee: integer("is_fee", { mode: "boolean" }).notNull(),
});

export const acquisitionLots = sqliteTable("acquisition_lots", {
  id: text().primaryKey().notNull(), // UUID stored as text
  acquiredLegId: text("acquired_leg_id")
    .notNull()
    .references(() => ledgerLegs.id),
  costPerUnit: text("cost_per_unit").notNull(), // Decimal string
});

export const disposalLinks = sqliteTable("disposal_links", {
  id: text().primaryKey().notNull(), // UUID stored as text
  disposalLegId: text("disposal_leg_id")
    .notNull()
    .references(() => ledgerLegs.id),
  lotId: text("lot_id")
    .notNull()
    .references(() => acquisitionLots.id),
  quantityUsed: text("quantity_used").notNull(), // Decimal string
  proceedsTotal: text("proceeds_total").notNull(), // Decimal string
});

export const taxEvents = sqliteTable("tax_events", {
  sourceId: text("source_id").primaryKey().notNull(), // UUID stored as text
  kind: text().notNull(),
  taxableGain: text("taxable_gain").notNull(), // Decimal string
});
