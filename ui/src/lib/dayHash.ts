const DAY_HASH_PREFIX = "#day-";
const DAY_ID_PREFIX = "day-";

export const hashForDay = (dayKey: string) => `${DAY_HASH_PREFIX}${dayKey}`;

export const dayKeyFromHash = (hash: string) => {
  if (!hash.startsWith(DAY_HASH_PREFIX)) return null;
  const key = hash.slice(DAY_HASH_PREFIX.length);
  return key.length > 0 ? key : null;
};

export const dayIdFor = (dayKey: string) => `${DAY_ID_PREFIX}${dayKey}`;
