import Decimal from "decimal.js";

import type { DecimalString } from "@/types/events";

const toNormalizedDecimalString = (value: Decimal): DecimalString => {
  if (value.isZero()) {
    return "0";
  }

  return value.toFixed();
};

const tryParseDecimalInput = (value: string): Decimal | null => {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return null;
  }

  try {
    return new Decimal(trimmedValue);
  } catch {
    return null;
  }
};

export const formatDecimalString = (value: DecimalString): string =>
  toNormalizedDecimalString(new Decimal(value));

export const getDecimalStringSign = (value: DecimalString): -1 | 0 | 1 => {
  const decimalValue = new Decimal(value);
  if (decimalValue.isZero()) {
    return 0;
  }

  return decimalValue.isNeg() ? -1 : 1;
};

export const normalizeDecimalInput = (value: string): DecimalString | null => {
  const decimalValue = tryParseDecimalInput(value);
  if (decimalValue === null) {
    return null;
  }

  return toNormalizedDecimalString(decimalValue);
};

export const isNonZeroDecimalString = (value: DecimalString): boolean =>
  getDecimalStringSign(value) !== 0;
