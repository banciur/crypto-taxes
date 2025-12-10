import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const ledgerEvents = sqliteTable("ledger_events", {
  id: text("id").primaryKey().notNull(), // UUID stored as text
  timestamp: text("timestamp").notNull(), // ISO-like DATETIME string
  ingestion: text("ingestion").notNull(),
  eventType: text("event_type").notNull(),
  originLocation: text("origin_location").notNull(),
  originExternalId: text("origin_external_id").notNull(),
});

export const ledgerLegs = sqliteTable("ledger_legs", {
  id: text("id").primaryKey().notNull(), // UUID stored as text
  eventId: text("event_id")
    .notNull()
    .references(() => ledgerEvents.id),
  assetId: text("asset_id").notNull(),
  quantity: text("quantity").notNull(), // Decimal string
  walletId: text("wallet_id").notNull(),
  isFee: integer("is_fee", { mode: "boolean" }).notNull(),
});

export const acquisitionLots = sqliteTable("acquisition_lots", {
  id: text("id").primaryKey().notNull(), // UUID stored as text
  acquiredLegId: text("acquired_leg_id")
    .notNull()
    .references(() => ledgerLegs.id),
  costPerUnit: text("cost_per_unit").notNull(), // Decimal string
});

export const disposalLinks = sqliteTable("disposal_links", {
  id: text("id").primaryKey().notNull(), // UUID stored as text
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
  kind: text("kind").notNull(),
  taxableGain: text("taxable_gain").notNull(), // Decimal string
});
