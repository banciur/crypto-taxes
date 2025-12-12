import { defineConfig } from "drizzle-kit";

export default defineConfig({
  out: "./drizzle",
  dialect: "sqlite",
  dbCredentials: { url: "../crypto_taxes.db" },
});
