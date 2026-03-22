"use client";

import { clsx } from "clsx";
import { Button } from "react-bootstrap";

type CorrectionRemoveButtonProps = {
  label: string;
  disabled: boolean;
  onClick: () => void;
  className?: string;
};

export function CorrectionRemoveButton({
  label,
  disabled,
  onClick,
  className,
}: CorrectionRemoveButtonProps) {
  return (
    <Button
      type="button"
      variant="link"
      className={clsx("p-0 text-danger", className)}
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
        <path
          fill="currentColor"
          d="M3.404 3.404a.75.75 0 0 1 1.06 0L8 6.939l3.536-3.535a.75.75 0 1 1 1.06 1.06L9.061 8l3.535 3.536a.75.75 0 1 1-1.06 1.06L8 9.061l-3.536 3.535a.75.75 0 1 1-1.06-1.06L6.939 8 3.404 4.464a.75.75 0 0 1 0-1.06Z"
        />
      </svg>
    </Button>
  );
}
