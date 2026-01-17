import Image from "next/image";

import { CHAIN_METADATA, type ChainKey } from "@/consts";

export type ChainIconProps = {
  place: string;
  size?: number;
  className?: string;
};

const formatChainLabel = (chainKey: string) =>
  `${chainKey.charAt(0).toUpperCase()}${chainKey.slice(1)}`;

export function ChainIcon({ place, size = 24, className }: ChainIconProps) {
  const chainKey = Object.hasOwn(CHAIN_METADATA, place)
    ? (place as ChainKey)
    : null;
  const label = chainKey ? formatChainLabel(chainKey) : "Unknown";
  const src = chainKey ? `/${chainKey}-logo.svg` : "/question-mark.svg";

  return (
    <Image
      src={src}
      alt={label}
      width={size}
      height={size}
      {...(className ? { className } : {})}
    />
  );
}
