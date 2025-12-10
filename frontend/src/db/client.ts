import path from "node:path";

import Database from "better-sqlite3";
import {BetterSQLite3Database, drizzle} from "drizzle-orm/better-sqlite3";
import { asc, desc } from "drizzle-orm";

import * as schema from "./schema";
import * as relations from "./relations";

const databaseFile = path.join(process.cwd(), "..", "crypto_taxes.db");

type LedgerEvent = typeof schema.ledgerEvents.$inferSelect;
type LedgerLeg = typeof schema.ledgerLegs.$inferSelect;

type LedgerEventWithLegs = LedgerEvent & {
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

export async function getLatestLedgerEvents(limit = 10): Promise<LedgerEventWithLegs[]> {
  const db = getClient();
  return db.query.ledgerEvents.findMany({
    limit,
    orderBy: desc(schema.ledgerEvents.timestamp),
    with: {
      ledgerLegs: {
        orderBy: asc(schema.ledgerLegs.id),
      },
    },
  });
}
