import path from "node:path";

import Database from "better-sqlite3";
import { BetterSQLite3Database, drizzle } from "drizzle-orm/better-sqlite3";
import { desc, eq } from "drizzle-orm";

import * as schema from "./schema";
import * as relations from "./relations";
import { ledgerEvents, ledgerLegs } from "./schema";

const databaseFile = path.join(process.cwd(), "..", "crypto_taxes.db");

type LedgerEvent = typeof schema.ledgerEvents.$inferSelect;
type LedgerLeg = typeof schema.ledgerLegs.$inferSelect;

export type LedgerEventWithLegs = LedgerEvent & {
  ledgerLegs: LedgerLeg[];
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
    .orderBy(desc(ledgerEvents.timestamp), ledgerEvents.id, ledgerLegs.id);

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
