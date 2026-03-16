"use client";

import { useMemo, useState } from "react";

import { Alert, Button, Col, Form, Modal, Row, Spinner } from "react-bootstrap";

import { getApiErrorMessage } from "@/api/core";
import { OriginId } from "@/components/OriginId";
import { useAccounts } from "@/contexts/AccountsContext";
import type {
  LedgerLeg,
  LedgerLegInput,
  ReplacementCorrectionCreatePayload,
} from "@/types/events";
import type { SelectableEvent } from "./selectableEvents";

type ReplacementEditorModalProps = {
  show: boolean;
  selectedEvents: SelectableEvent[];
  isSubmitting: boolean;
  onHide: () => void;
  onSubmit: (payload: ReplacementCorrectionCreatePayload) => Promise<void>;
};

type ReplacementLegDraft = LedgerLegInput & {
  key: string;
};

const padTimestampPart = (value: number) => String(value).padStart(2, "0");

const utcTimestampInputValue = (timestamp: string) => {
  const date = new Date(timestamp);
  return `${date.getUTCFullYear()}-${padTimestampPart(
    date.getUTCMonth() + 1,
  )}-${padTimestampPart(date.getUTCDate())}T${padTimestampPart(
    date.getUTCHours(),
  )}:${padTimestampPart(date.getUTCMinutes())}:${padTimestampPart(
    date.getUTCSeconds(),
  )}`;
};

const ledgerLegDraft = (leg?: LedgerLeg): ReplacementLegDraft => ({
  key: crypto.randomUUID(),
  assetId: leg?.assetId ?? "",
  accountChainId: leg?.accountChainId ?? "",
  quantity: leg?.quantity ?? "",
  isFee: leg?.isFee ?? false,
});

const initialTimestampValue = (selectedEvents: SelectableEvent[]) =>
  selectedEvents.length === 1
    ? utcTimestampInputValue(selectedEvents[0].timestamp)
    : "";

const initialLegDrafts = (selectedEvents: SelectableEvent[]) =>
  selectedEvents.length === 1
    ? selectedEvents[0].legs.map((leg) => ledgerLegDraft(leg))
    : [ledgerLegDraft()];

const validateReplacementDraft = (
  timestampInput: string,
  legs: ReplacementLegDraft[],
) => {
  if (timestampInput.length === 0) {
    return "Replacement timestamp is required.";
  }

  if (legs.length === 0) {
    return "At least one replacement leg is required.";
  }

  for (const [index, leg] of legs.entries()) {
    const assetId = leg.assetId.trim();
    const accountChainId = leg.accountChainId.trim();
    const quantity = leg.quantity.trim();

    if (assetId.length === 0) {
      return `Leg ${index + 1} is missing an asset ID.`;
    }

    if (accountChainId.length === 0) {
      return `Leg ${index + 1} is missing an account.`;
    }

    if (quantity.length === 0) {
      return `Leg ${index + 1} is missing a quantity.`;
    }

    const parsedQuantity = Number(quantity);
    if (!Number.isFinite(parsedQuantity) || parsedQuantity === 0) {
      return `Leg ${index + 1} must have a non-zero numeric quantity.`;
    }
  }

  return null;
};

const replacementPayload = (
  selectedEvents: SelectableEvent[],
  timestampInput: string,
  legs: ReplacementLegDraft[],
): ReplacementCorrectionCreatePayload => ({
  timestamp: `${timestampInput}Z`,
  sources: selectedEvents.map((event) => event.eventOrigin),
  legs: legs.map((leg) => ({
    assetId: leg.assetId.trim(),
    accountChainId: leg.accountChainId.trim(),
    quantity: leg.quantity.trim(),
    isFee: leg.isFee,
  })),
});

export function ReplacementEditorModal({
  show,
  selectedEvents,
  isSubmitting,
  onHide,
  onSubmit,
}: ReplacementEditorModalProps) {
  const accounts = useAccounts();

  const orderedSelectedEvents = useMemo(
    () =>
      [...selectedEvents].sort(
        (left, right) =>
          left.timestamp.localeCompare(right.timestamp) ||
          left.eventOrigin.location.localeCompare(right.eventOrigin.location) ||
          left.eventOrigin.externalId.localeCompare(
            right.eventOrigin.externalId,
          ),
      ),
    [selectedEvents],
  );

  const orderedAccounts = useMemo(
    () =>
      [...accounts].sort(
        (left, right) =>
          left.name.localeCompare(right.name) ||
          left.accountChainId.localeCompare(right.accountChainId),
      ),
    [accounts],
  );
  const [timestampInput, setTimestampInput] = useState(() =>
    initialTimestampValue(orderedSelectedEvents),
  );
  const [legs, setLegs] = useState<ReplacementLegDraft[]>(() =>
    initialLegDrafts(orderedSelectedEvents),
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const updateLeg = (
    key: string,
    update: Partial<Omit<ReplacementLegDraft, "key">>,
  ) => {
    setErrorMessage(null);
    setLegs((current) =>
      current.map((leg) => (leg.key === key ? { ...leg, ...update } : leg)),
    );
  };

  const addLeg = () => {
    setErrorMessage(null);
    setLegs((current) => [...current, ledgerLegDraft()]);
  };

  const removeLeg = (key: string) => {
    setErrorMessage(null);
    setLegs((current) => current.filter((leg) => leg.key !== key));
  };

  const handleSubmit = async () => {
    const validationError = validateReplacementDraft(timestampInput, legs);
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }

    try {
      await onSubmit(
        replacementPayload(orderedSelectedEvents, timestampInput, legs),
      );
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    }
  };

  return (
    <Modal
      show={show}
      onHide={isSubmitting ? undefined : onHide}
      size="lg"
      centered
    >
      <Modal.Header closeButton={!isSubmitting}>
        <Modal.Title>Create replacement</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {errorMessage ? (
          <Alert variant="danger" className="mb-3">
            {errorMessage}
          </Alert>
        ) : null}

        <div className="mb-4">
          <div className="mb-2 small text-muted">Sources</div>
          <div className="d-flex flex-column gap-2">
            {orderedSelectedEvents.map((event) => (
              <div
                key={`${event.eventOrigin.location}:${event.eventOrigin.externalId}`}
                className="d-flex flex-wrap align-items-center gap-2 rounded border px-3 py-2"
              >
                <OriginId
                  originId={event.eventOrigin.externalId}
                  place={event.eventOrigin.location.toLowerCase()}
                  className="small text-muted"
                />
                <span className="small text-muted">
                  {new Date(event.timestamp).toLocaleString("en-GB", {
                    timeZone: "UTC",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    year: "numeric",
                    month: "2-digit",
                    day: "2-digit",
                  })}{" "}
                  UTC
                </span>
              </div>
            ))}
          </div>
        </div>

        <Form.Group className="mb-4">
          <Form.Label>Timestamp (UTC)</Form.Label>
          <Form.Control
            type="datetime-local"
            step={1}
            value={timestampInput}
            disabled={isSubmitting}
            onChange={(event) => {
              setErrorMessage(null);
              setTimestampInput(event.target.value);
            }}
          />
          <Form.Text>
            Enter the authoritative replacement timestamp in UTC.
          </Form.Text>
        </Form.Group>

        <div className="mb-2 d-flex flex-wrap align-items-center justify-content-between gap-2">
          <Form.Label className="mb-0">Legs</Form.Label>
          <Button
            type="button"
            variant="outline-secondary"
            size="sm"
            disabled={isSubmitting}
            onClick={addLeg}
          >
            Add leg
          </Button>
        </div>

        <div className="d-flex flex-column gap-3">
          {legs.map((leg, index) => (
            <div key={leg.key} className="rounded border p-3">
              <div className="mb-3 d-flex flex-wrap align-items-center justify-content-between gap-2">
                <span className="fw-semibold">Leg {index + 1}</span>
                <Button
                  type="button"
                  variant="link"
                  className="p-0 text-danger"
                  disabled={isSubmitting || legs.length <= 1}
                  onClick={() => removeLeg(leg.key)}
                >
                  Remove
                </Button>
              </div>

              <Row className="g-3">
                <Col md={4}>
                  <Form.Group>
                    <Form.Label>Asset ID</Form.Label>
                    <Form.Control
                      type="text"
                      value={leg.assetId}
                      disabled={isSubmitting}
                      onChange={(event) =>
                        updateLeg(leg.key, { assetId: event.target.value })
                      }
                    />
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label>Account</Form.Label>
                    <Form.Select
                      value={leg.accountChainId}
                      disabled={isSubmitting}
                      onChange={(event) =>
                        updateLeg(leg.key, {
                          accountChainId: event.target.value,
                        })
                      }
                    >
                      <option value="">Select account</option>
                      {orderedAccounts.map((account) => (
                        <option
                          key={account.accountChainId}
                          value={account.accountChainId}
                        >
                          {account.name} ({account.location})
                        </option>
                      ))}
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label>Quantity</Form.Label>
                    <Form.Control
                      type="text"
                      value={leg.quantity}
                      disabled={isSubmitting}
                      onChange={(event) =>
                        updateLeg(leg.key, { quantity: event.target.value })
                      }
                    />
                  </Form.Group>
                </Col>
                <Col xs={12}>
                  <Form.Check
                    type="checkbox"
                    id={`replacement-leg-fee-${leg.key}`}
                    label="Fee leg"
                    checked={leg.isFee}
                    disabled={isSubmitting}
                    onChange={(event) =>
                      updateLeg(leg.key, { isFee: event.target.checked })
                    }
                  />
                </Col>
              </Row>
            </div>
          ))}
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button
          type="button"
          variant="outline-secondary"
          disabled={isSubmitting}
          onClick={onHide}
        >
          Cancel
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={isSubmitting}
          onClick={handleSubmit}
        >
          {isSubmitting ? (
            <>
              <Spinner size="sm" className="me-2" />
              Saving...
            </>
          ) : (
            "Save replacement"
          )}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
