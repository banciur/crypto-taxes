import Image from "next/image";

import { CHAIN_METADATA, type ChainKey } from "@/consts";

export type OriginIconProps = {
  place: string;
  size?: number;
  className?: string;
};

const formatOriginLabel = (originKey: string) =>
  `${originKey.charAt(0).toUpperCase()}${originKey.slice(1)}`;

export function OriginIcon({ place, size = 24, className }: OriginIconProps) {
  const originKey = Object.hasOwn(CHAIN_METADATA, place)
    ? (place as ChainKey)
    : null;
  const label = originKey ? formatOriginLabel(originKey) : "Unknown";
  const src = originKey ? `/${originKey}-logo.svg` : "/question-mark.svg";

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
