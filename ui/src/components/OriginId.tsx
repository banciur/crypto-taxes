"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
} from "react";
import { Overlay, Popover } from "react-bootstrap";

import { CHAIN_METADATA, type ChainKey } from "@/consts";
import styles from "./OriginId.module.css";

export type OriginIdProps = {
  originId: string;
  place: string;
  className?: string;
};

const formatOriginId = (originId: string): ReactNode => {
  if (originId.length <= 8) {
    return originId;
  }
  const prefix = originId.slice(0, 5);
  const suffix = originId.slice(-3);
  return (
    <>
      {prefix}&hellip;{suffix}
    </>
  );
};

export function OriginId({ originId, place, className }: OriginIdProps) {
  const [show, setShow] = useState(false);
  const [copied, setCopied] = useState(false);
  const instanceId = useId();
  const [targetElement, setTargetElement] = useState<HTMLElement | null>(null);
  const copyTimeoutRef = useRef<number | null>(null);
  const chainKey = Object.hasOwn(CHAIN_METADATA, place)
    ? (place as ChainKey)
    : null;
  const label = formatOriginId(originId);

  useEffect(() => {
    const handleOpen = (event: Event) => {
      const customEvent = event as CustomEvent<{ id?: string }>;
      if (customEvent.detail?.id !== instanceId) {
        setShow(false);
      }
    };

    window.addEventListener("originid:open", handleOpen);
    return () => {
      window.removeEventListener("originid:open", handleOpen);
    };
  }, [instanceId]);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current !== null) {
        window.clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  const openPopover = () => {
    window.dispatchEvent(
      new CustomEvent("originid:open", { detail: { id: instanceId } }),
    );
    setShow(true);
  };

  const handleCopy = async (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    await navigator.clipboard.writeText(originId);
    setCopied(true);
    if (copyTimeoutRef.current !== null) {
      window.clearTimeout(copyTimeoutRef.current);
    }
    copyTimeoutRef.current = window.setTimeout(() => {
      setCopied(false);
    }, 1200);
  };

  const copyButtonClassName = copied
    ? `${styles.copyButton} ${styles.copyButtonCopied}`
    : styles.copyButton;
  const popover = (
    <Popover id={`origin-id-${originId}`} className={styles.popover}>
      <Popover.Body className={styles.popoverBody}>
        <span className="text-nowrap">{originId}</span>
        <button
          type="button"
          className={copyButtonClassName}
          onClick={handleCopy}
          aria-label="Copy origin id"
          title="Copy origin id"
        >
          {copied ? (
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M13.485 1.929a1 1 0 0 1 1.414 1.414l-8 8a1 1 0 0 1-1.414 0l-3-3a1 1 0 1 1 1.414-1.414L6 9.414l7.485-7.485z" />
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M10 1.5H4A1.5 1.5 0 0 0 2.5 3v7H4V3a.5.5 0 0 1 .5-.5H10V1.5z" />
              <path d="M5.5 5A1.5 1.5 0 0 1 7 3.5h5A1.5 1.5 0 0 1 13.5 5v8A1.5 1.5 0 0 1 12 14.5H7A1.5 1.5 0 0 1 5.5 13V5zM7 4.5a.5.5 0 0 0-.5.5v8a.5.5 0 0 0 .5.5h5a.5.5 0 0 0 .5-.5V5a.5.5 0 0 0-.5-.5H7z" />
            </svg>
          )}
        </button>
      </Popover.Body>
    </Popover>
  );

  const overlay = targetElement ? (
    <Overlay
      target={targetElement}
      show={show}
      placement="bottom"
      rootClose
      onHide={() => setShow(false)}
    >
      {popover}
    </Overlay>
  ) : null;
  const labelElement = chainKey ? (
    <a
      className={className}
      href={`${CHAIN_METADATA[chainKey].tracker}tx/${originId}`}
      target="_blank"
      rel="noreferrer"
    >
      {label}
    </a>
  ) : (
    <span className={className} role="button" tabIndex={0}>
      {label}
    </span>
  );
  return (
    <span
      ref={setTargetElement}
      className={styles.container}
      onMouseEnter={openPopover}
      onFocus={openPopover}
    >
      {labelElement}
      {overlay}
    </span>
  );
}
