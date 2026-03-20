import {
  formatDecimalString,
  getDecimalStringSign,
} from "@/lib/decimalStrings";
import type { LedgerLeg } from "@/types/events";

type LedgerLegQuantityPresentation = {
  className?: string;
  text: string;
};

type LedgerLegQuantityInput = Pick<LedgerLeg, "isFee" | "quantity">;

export const getLedgerLegQuantityPresentation = ({
  isFee,
  quantity,
}: LedgerLegQuantityInput): LedgerLegQuantityPresentation => {
  const text = formatDecimalString(quantity);

  if (isFee) {
    return {
      className: "text-info",
      text,
    };
  }

  const sign = getDecimalStringSign(quantity);
  if (sign < 0) {
    return {
      className: "text-danger",
      text,
    };
  }

  if (sign > 0) {
    return {
      className: "text-success",
      text,
    };
  }

  return { text };
};
