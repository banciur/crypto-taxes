export const orderByTimestamp = <T extends { id: string; timestamp: string }>(
  items: T[],
): T[] =>
  [...items].sort((a, b) => {
    const aTime = Date.parse(a.timestamp);
    const bTime = Date.parse(b.timestamp);
    if (aTime !== bTime) {
      return bTime - aTime;
    }
    return a.id.localeCompare(b.id);
  });
