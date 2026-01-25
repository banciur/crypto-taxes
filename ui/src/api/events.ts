const DEFAULT_API_BASE_URL = "http://localhost:8000";
const API_BASE_URL = process.env.CRYPTO_TAXES_API_URL ?? DEFAULT_API_BASE_URL;
const MAX_EVENTS = 300;

export type ApiEventOrigin = {
  location: string;
  external_id: string;
};

export type ApiLedgerLeg = {
  id: string;
  asset_id: string;
  wallet_id: string;
  quantity: string;
  is_fee: boolean;
};

export type ApiLedgerEvent = {
  id: string;
  timestamp: string;
  origin: ApiEventOrigin;
  ingestion: string;
  event_type: string;
  legs: ApiLedgerLeg[];
};

export type ApiSeedEvent = {
  id: string;
  timestamp: string;
  price_per_token: string;
  legs: ApiLedgerLeg[];
};

const buildUrl = (path: string) => {
  const normalizedBase = API_BASE_URL.endsWith("/")
    ? API_BASE_URL
    : `${API_BASE_URL}/`;
  const normalizedPath = path.startsWith("/") ? path.slice(1) : path;
  return new URL(normalizedPath, normalizedBase).toString();
};

const fetchApi = async <T>(path: string): Promise<T> => {
  const response = await fetch(buildUrl(path), { cache: "no-store" });
  if (!response.ok) {
    const details = await response.text().catch(() => "missing details");
    throw new Error(`Failed to fetch ${path}: ${response.status} : ${details}`);
  }
  return (await response.json()) as T;
};

const orderEvents = <T extends { id: string; timestamp: string }>(
  events: T[],
) =>
  [...events]
    .sort((a, b) => {
      const aTime = Date.parse(a.timestamp);
      const bTime = Date.parse(b.timestamp);
      if (aTime !== bTime) {
        return bTime - aTime;
      }
      return a.id.localeCompare(b.id);
    })
    .slice(0, MAX_EVENTS);

export const getRawEvents = async (): Promise<ApiLedgerEvent[]> => {
  const events = await fetchApi<ApiLedgerEvent[]>("/raw-events");
  return orderEvents(events);
};

export const getCorrectedEvents = async (): Promise<ApiLedgerEvent[]> => {
  const events = await fetchApi<ApiLedgerEvent[]>("/corrected-events");
  return orderEvents(events);
};

export const getSeedEvents = async (): Promise<ApiSeedEvent[]> => {
  const events = await fetchApi<ApiSeedEvent[]>("/seed-events");
  return orderEvents(events);
};
