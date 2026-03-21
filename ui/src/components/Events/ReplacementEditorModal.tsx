"use client";

import { useMemo, useState } from "react";

import {
  Alert,
  Button,
  Col,
  Form,
  ListGroup,
  Modal,
  Row,
} from "react-bootstrap";

import { useAccountNames } from "@/contexts/AccountNamesContext";
import {
  formatDecimalString,
  isNonZeroDecimalString,
  normalizeDecimalInput,
} from "@/lib/decimalStrings";
import type {
  CreateLedgerCorrectionPayload,
  LedgerEvent,
  LedgerCorrectionDraftLeg,
} from "@/types/events";

type DraftLeg = LedgerCorrectionDraftLeg & {
  draftId: string;
};

type ReplacementEditorModalProps = {
  show: boolean;
  selectedSourceEvents: readonly LedgerEvent[];
  isSaving: boolean;
  errorMessage: string | null;
  onHide: () => void;
  onSubmit: (payload: CreateLedgerCorrectionPayload) => Promise<void>;
};

const createDraftLeg = (leg: LedgerCorrectionDraftLeg): DraftLeg => ({
  ...leg,
  draftId: crypto.randomUUID(),
});

const formatUtcDateInput = (timestamp: string) => timestamp.slice(0, 10);

const formatUtcTimeInput = (timestamp: string) => timestamp.slice(11, 19);

const combineUtcTimestamp = (date: string, time: string): string | null => {
  if (!date || !time) {
    return null;
  }

  const [year, month, day] = date.split("-").map(Number);
  const [hours, minutes, seconds = 0] = time.split(":").map(Number);
  if (
    [year, month, day, hours, minutes, seconds].some((value) =>
      Number.isNaN(value),
    )
  ) {
    return null;
  }

  return new Date(
    Date.UTC(year, month - 1, day, hours, minutes, seconds),
  ).toISOString();
};

const latestSourceTimestamp = (
  selectedSourceEvents: readonly LedgerEvent[],
): string | null =>
  selectedSourceEvents
    .map((sourceEvent) => sourceEvent.timestamp)
    .sort()
    .at(-1) ?? null;

const buildInitialDraftLegs = (
  selectedSourceEvents: readonly LedgerEvent[],
  resolveAccountName: (accountChainId: string) => string,
): DraftLeg[] =>
  selectedSourceEvents
    .flatMap((sourceEvent) => sourceEvent.legs)
    .slice()
    .sort((left, right) => {
      const byAssetId = left.assetId.localeCompare(right.assetId);
      if (byAssetId !== 0) {
        return byAssetId;
      }

      const byAccountName = resolveAccountName(
        left.accountChainId,
      ).localeCompare(resolveAccountName(right.accountChainId));
      if (byAccountName !== 0) {
        return byAccountName;
      }

      return left.accountChainId.localeCompare(right.accountChainId);
    })
    .map((leg) =>
      createDraftLeg({
        assetId: leg.assetId,
        accountChainId: leg.accountChainId,
        quantity: formatDecimalString(leg.quantity),
        isFee: leg.isFee,
      }),
    );

export function ReplacementEditorModal({
  show,
  selectedSourceEvents,
  isSaving,
  errorMessage,
  onHide,
  onSubmit,
}: ReplacementEditorModalProps) {
  const { accounts, resolveAccountName } = useAccountNames();
  const initialTimestamp = latestSourceTimestamp(selectedSourceEvents);
  const [timestampDate, setTimestampDate] = useState(() =>
    initialTimestamp ? formatUtcDateInput(initialTimestamp) : "",
  );
  const [timestampTime, setTimestampTime] = useState(() =>
    initialTimestamp ? formatUtcTimeInput(initialTimestamp) : "",
  );
  const [draftLegs, setDraftLegs] = useState<DraftLeg[]>(() =>
    buildInitialDraftLegs(selectedSourceEvents, resolveAccountName),
  );
  const [note, setNote] = useState("");
  const [validationMessage, setValidationMessage] = useState<string | null>(
    null,
  );

  const sortedAccounts = useMemo(
    () =>
      [...accounts].sort(
        (left, right) =>
          left.displayName.localeCompare(right.displayName) ||
          left.accountChainId.localeCompare(right.accountChainId),
      ),
    [accounts],
  );

  const handleLegChange = <K extends keyof LedgerCorrectionDraftLeg>(
    draftId: string,
    key: K,
    value: LedgerCorrectionDraftLeg[K],
  ) => {
    setDraftLegs((current) =>
      current.map((leg) =>
        leg.draftId === draftId ? { ...leg, [key]: value } : leg,
      ),
    );
  };

  const handleAddLeg = () => {
    setDraftLegs((current) => [
      ...current,
      createDraftLeg({
        assetId: "",
        accountChainId: "",
        quantity: "",
        isFee: false,
      }),
    ]);
  };

  const handleRemoveLeg = (draftId: string) => {
    setDraftLegs((current) => current.filter((leg) => leg.draftId !== draftId));
  };

  const handleSubmit = async () => {
    const timestamp = combineUtcTimestamp(timestampDate, timestampTime);
    if (!timestamp) {
      setValidationMessage(
        "Replacement timestamp is required and must be valid UTC date/time.",
      );
      return;
    }

    if (draftLegs.length === 0) {
      setValidationMessage("Replacement must contain at least one leg.");
      return;
    }

    const normalizedLegs: LedgerCorrectionDraftLeg[] = [];
    for (const leg of draftLegs) {
      const assetId = leg.assetId.trim();
      const accountChainId = leg.accountChainId.trim();
      const quantityInput = leg.quantity.trim();

      if (!assetId || !accountChainId || !quantityInput) {
        setValidationMessage(
          "Each leg must include asset, account, and quantity.",
        );
        return;
      }

      const quantity = normalizeDecimalInput(quantityInput);
      if (quantity === null || !isNonZeroDecimalString(quantity)) {
        setValidationMessage(
          "Each leg quantity must be a valid non-zero decimal.",
        );
        return;
      }

      normalizedLegs.push({
        assetId,
        accountChainId,
        quantity,
        isFee: leg.isFee,
      });
    }

    setValidationMessage(null);
    await onSubmit({
      timestamp,
      sources: selectedSourceEvents.map(
        (sourceEvent) => sourceEvent.eventOrigin,
      ),
      legs: normalizedLegs,
      note: note.trim(),
    });
  };

  return (
    <Modal
      show={show}
      onHide={isSaving ? undefined : onHide}
      size="xl"
      centered
    >
      <Modal.Header closeButton={!isSaving}>
        <Modal.Title>Create Replacement</Modal.Title>
      </Modal.Header>
      <Modal.Body className="d-flex flex-column gap-3">
        <div>
          <div className="small fw-semibold text-uppercase text-muted">
            Sources
          </div>
          <ListGroup className="mt-2">
            {selectedSourceEvents.map((sourceEvent) => (
              <ListGroup.Item
                key={`${sourceEvent.eventOrigin.location}:${sourceEvent.eventOrigin.externalId}`}
              >
                <div className="fw-semibold">
                  {sourceEvent.eventOrigin.location}/
                  {sourceEvent.eventOrigin.externalId}
                </div>
                <div className="small text-muted">{sourceEvent.timestamp}</div>
              </ListGroup.Item>
            ))}
          </ListGroup>
        </div>

        <Row className="g-3">
          <Col md={6}>
            <Form.Group controlId="replacement-timestamp-date">
              <Form.Label>Date (UTC)</Form.Label>
              <Form.Control
                type="date"
                value={timestampDate}
                disabled={isSaving}
                onChange={(event) => setTimestampDate(event.target.value)}
              />
            </Form.Group>
          </Col>
          <Col md={6}>
            <Form.Group controlId="replacement-timestamp-time">
              <Form.Label>Time (UTC)</Form.Label>
              <Form.Control
                type="time"
                step={1}
                value={timestampTime}
                disabled={isSaving}
                onChange={(event) => setTimestampTime(event.target.value)}
              />
            </Form.Group>
          </Col>
        </Row>

        <div className="d-flex align-items-center justify-content-between">
          <div className="small fw-semibold text-uppercase text-muted">
            Legs
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline-secondary"
            disabled={isSaving}
            onClick={handleAddLeg}
          >
            Add leg
          </Button>
        </div>

        <div className="d-flex flex-column gap-3">
          {draftLegs.map((leg) => (
            <div key={leg.draftId} className="rounded border p-3">
              <Row className="g-3">
                <Col md={3}>
                  <Form.Group
                    controlId={`replacement-leg-asset-${leg.draftId}`}
                  >
                    <Form.Label>Asset</Form.Label>
                    <Form.Control
                      type="text"
                      value={leg.assetId}
                      disabled={isSaving}
                      onChange={(event) =>
                        handleLegChange(
                          leg.draftId,
                          "assetId",
                          event.target.value,
                        )
                      }
                    />
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group
                    controlId={`replacement-leg-account-${leg.draftId}`}
                  >
                    <Form.Label>Account</Form.Label>
                    <Form.Select
                      value={leg.accountChainId}
                      disabled={isSaving}
                      onChange={(event) =>
                        handleLegChange(
                          leg.draftId,
                          "accountChainId",
                          event.target.value,
                        )
                      }
                    >
                      <option value="">Select account</option>
                      {sortedAccounts.map((account) => (
                        <option
                          key={account.accountChainId}
                          value={account.accountChainId}
                        >
                          {account.displayName}
                        </option>
                      ))}
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={3}>
                  <Form.Group
                    controlId={`replacement-leg-quantity-${leg.draftId}`}
                  >
                    <Form.Label>Quantity</Form.Label>
                    <Form.Control
                      type="text"
                      value={leg.quantity}
                      disabled={isSaving}
                      onChange={(event) =>
                        handleLegChange(
                          leg.draftId,
                          "quantity",
                          event.target.value,
                        )
                      }
                    />
                  </Form.Group>
                </Col>
                <Col md={2} className="d-flex align-items-end">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline-danger"
                    disabled={isSaving}
                    onClick={() => handleRemoveLeg(leg.draftId)}
                  >
                    Remove
                  </Button>
                </Col>
              </Row>

              <Form.Check
                className="mt-3"
                type="checkbox"
                id={`replacement-leg-fee-${leg.draftId}`}
                label="Fee leg"
                checked={leg.isFee}
                disabled={isSaving}
                onChange={(event) =>
                  handleLegChange(leg.draftId, "isFee", event.target.checked)
                }
              />
            </div>
          ))}
        </div>

        <Form.Group controlId="replacement-note">
          <Form.Label>Note</Form.Label>
          <Form.Control
            as="textarea"
            rows={3}
            value={note}
            disabled={isSaving}
            onChange={(event) => setNote(event.target.value)}
          />
        </Form.Group>

        {(validationMessage || errorMessage) && (
          <Alert variant="danger" className="mb-0">
            {validationMessage ?? errorMessage}
          </Alert>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button
          type="button"
          variant="secondary"
          disabled={isSaving}
          onClick={onHide}
        >
          Cancel
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={isSaving}
          onClick={handleSubmit}
        >
          {isSaving ? "Saving..." : "Save replacement"}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
