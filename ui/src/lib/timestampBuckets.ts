export const timestampBucketKeyFor = (timestamp: string) =>
  String(Math.floor(new Date(timestamp).getTime() / 1000));

export const dayKeyForTimestampBucket = (timestampBucket: string) =>
  new Date(Number(timestampBucket) * 1000).toISOString().slice(0, 10);
