import path from "node:path";

import Database from "better-sqlite3";
import { BetterSQLite3Database, drizzle } from "drizzle-orm/better-sqlite3";
import { desc, eq } from "drizzle-orm";

import * as schema from "./schema";
import * as relations from "./relations";
import {
  ledgerEvents,
  ledgerLegs,
  correctedLedgerEvents,
  correctedLedgerLegs,
  seedEvents,
  seedEventLegs,
} from "./schema";

const databaseFile = path.join(process.cwd(), "..", "crypto_taxes.db");

type LedgerEvent = typeof schema.ledgerEvents.$inferSelect;
type LedgerLeg = typeof schema.ledgerLegs.$inferSelect;
type CorrectedLedgerEvent = typeof schema.correctedLedgerEvents.$inferSelect;
type CorrectedLedgerLeg = typeof schema.correctedLedgerLegs.$inferSelect;
type SeedEvent = typeof schema.seedEvents.$inferSelect;
type SeedEventLeg = typeof schema.seedEventLegs.$inferSelect;

export type LedgerEventWithLegs = LedgerEvent & {
  ledgerLegs: LedgerLeg[];
};

export type SeedEventWithLegs = SeedEvent & {
  seedEventLegs: SeedEventLeg[];
};

export type CorrectedLedgerEventWithLegs = CorrectedLedgerEvent & {
  correctedLedgerLegs: CorrectedLedgerLeg[];
};

type DB = BetterSQLite3Database<typeof schema & typeof relations>;

let client: DB | null = null;

function getClient(): DB {
  if (client) {
    return client;
  }
  const sqlite = new Database(databaseFile, { readonly: true });
  client = drizzle(sqlite, { schema: { ...schema, ...relations } });
  return client;
}

export async function getLedgerEvents(): Promise<LedgerEventWithLegs[]> {
  const db = getClient();

  const rows = await db
    .select({ event: ledgerEvents, leg: ledgerLegs })
    .from(ledgerEvents)
    .leftJoin(ledgerLegs, eq(ledgerEvents.id, ledgerLegs.eventId))
    .orderBy(desc(ledgerEvents.timestamp), ledgerEvents.id, ledgerLegs.id)
    .limit(100);

  const eventsById = new Map<string, LedgerEventWithLegs>();
  const orderedEvents: LedgerEventWithLegs[] = [];

  for (const { event, leg } of rows) {
    let eventWithLegs = eventsById.get(event.id);
    if (!eventWithLegs) {
      eventWithLegs = { ...event, ledgerLegs: [] };
      eventsById.set(event.id, eventWithLegs);
      orderedEvents.push(eventWithLegs);
    }

    if (leg) {
      eventWithLegs.ledgerLegs.push(leg);
    }
  }

  return orderedEvents;
}

export async function getSeedEvents(): Promise<SeedEventWithLegs[]> {
  const db = getClient();

  const rows = await db
    .select({ event: seedEvents, leg: seedEventLegs })
    .from(seedEvents)
    .leftJoin(seedEventLegs, eq(seedEvents.id, seedEventLegs.eventId))
    .orderBy(desc(seedEvents.timestamp), seedEvents.id, seedEventLegs.id)
    .limit(100);

  const eventsById = new Map<string, SeedEventWithLegs>();
  const orderedEvents: SeedEventWithLegs[] = [];

  for (const { event, leg } of rows) {
    let eventWithLegs = eventsById.get(event.id);
    if (!eventWithLegs) {
      eventWithLegs = { ...event, seedEventLegs: [] };
      eventsById.set(event.id, eventWithLegs);
      orderedEvents.push(eventWithLegs);
    }

    if (leg) {
      eventWithLegs.seedEventLegs.push(leg);
    }
  }

  return orderedEvents;
}

export async function getCorrectedLedgerEvents(): Promise<
  CorrectedLedgerEventWithLegs[]
> {
  const db = getClient();

  const rows = await db
    .select({ event: correctedLedgerEvents, leg: correctedLedgerLegs })
    .from(correctedLedgerEvents)
    .leftJoin(
      correctedLedgerLegs,
      eq(correctedLedgerEvents.id, correctedLedgerLegs.eventId),
    )
    .orderBy(
      desc(correctedLedgerEvents.timestamp),
      correctedLedgerEvents.id,
      correctedLedgerLegs.id,
    )
    .limit(100);

  const eventsById = new Map<string, CorrectedLedgerEventWithLegs>();
  const orderedEvents: CorrectedLedgerEventWithLegs[] = [];

  for (const { event, leg } of rows) {
    let eventWithLegs = eventsById.get(event.id);
    if (!eventWithLegs) {
      eventWithLegs = { ...event, correctedLedgerLegs: [] };
      eventsById.set(event.id, eventWithLegs);
      orderedEvents.push(eventWithLegs);
    }

    if (leg) {
      eventWithLegs.correctedLedgerLegs.push(leg);
    }
  }

  return orderedEvents;
}
