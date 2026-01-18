import { CHAIN_METADATA, type ChainKey } from "@/consts";

export type TxHashProps = {
  hash: string;
  place: string;
  className?: string;
};

const formatTxHash = (hash: string) => {
  if (hash.length <= 8) {
    return hash;
  }
  const prefix = hash.slice(0, 5);
  const suffix = hash.slice(-3);
  return (
    <>
      {prefix}&hellip;{suffix}
    </>
  );
};

export function TxHash({ hash, place, className }: TxHashProps) {
  const chainKey = Object.hasOwn(CHAIN_METADATA, place)
    ? (place as ChainKey)
    : null;
  const label = formatTxHash(hash);

  if (!chainKey) {
    return <span className={className}>{label}</span>;
  }

  const href = `${CHAIN_METADATA[chainKey].tracker}tx/${hash}`;
  return (
    <a className={className} href={href} target="_blank" rel="noreferrer">
      {label}
    </a>
  );
}
