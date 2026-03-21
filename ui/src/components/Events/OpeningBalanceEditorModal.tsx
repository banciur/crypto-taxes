"use client";

import { useMemo, useState } from "react";

import { Alert, Button, Col, Form, Modal, Row } from "react-bootstrap";

import { useAccountNames } from "@/contexts/AccountNamesContext";
import {
  getDecimalStringSign,
  normalizeDecimalInput,
} from "@/lib/decimalStrings";
import type {
  CreateLedgerCorrectionPayload,
  LedgerCorrectionDraftLeg,
} from "@/types/events";

type OpeningBalanceEditorModalProps = {
  show: boolean;
  isSaving: boolean;
  errorMessage: string | null;
  onHide: () => void;
  onSubmit: (payload: CreateLedgerCorrectionPayload) => Promise<void>;
};

const nowUtcIsoString = () => new Date().toISOString();

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

export function OpeningBalanceEditorModal({
  show,
  isSaving,
  errorMessage,
  onHide,
  onSubmit,
}: OpeningBalanceEditorModalProps) {
  const { accounts } = useAccountNames();
  const initialTimestamp = nowUtcIsoString();
  const [timestampDate, setTimestampDate] = useState(() =>
    formatUtcDateInput(initialTimestamp),
  );
  const [timestampTime, setTimestampTime] = useState(() =>
    formatUtcTimeInput(initialTimestamp),
  );
  const [assetId, setAssetId] = useState("");
  const [accountChainId, setAccountChainId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [pricePerToken, setPricePerToken] = useState("");
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

  const handleSubmit = async () => {
    const timestamp = combineUtcTimestamp(timestampDate, timestampTime);
    if (!timestamp) {
      setValidationMessage(
        "Opening balance timestamp is required and must be valid UTC date/time.",
      );
      return;
    }

    const normalizedQuantity = normalizeDecimalInput(quantity);
    if (
      !assetId.trim() ||
      !accountChainId.trim() ||
      normalizedQuantity === null ||
      getDecimalStringSign(normalizedQuantity) <= 0
    ) {
      setValidationMessage(
        "Opening balance requires asset, account, and a positive quantity.",
      );
      return;
    }

    const normalizedPricePerToken =
      pricePerToken.trim() === "" ? null : normalizeDecimalInput(pricePerToken);
    if (normalizedPricePerToken === null && pricePerToken.trim() !== "") {
      setValidationMessage("Price per token must be a valid decimal.");
      return;
    }
    if (
      normalizedPricePerToken !== null &&
      getDecimalStringSign(normalizedPricePerToken) < 0
    ) {
      setValidationMessage("Price per token must be zero or positive.");
      return;
    }

    const legs: LedgerCorrectionDraftLeg[] = [
      {
        assetId: assetId.trim(),
        accountChainId: accountChainId.trim(),
        quantity: normalizedQuantity,
        isFee: false,
      },
    ];

    setValidationMessage(null);
    await onSubmit({
      timestamp,
      sources: [],
      legs,
      pricePerToken: normalizedPricePerToken,
      note: note.trim(),
    });
  };

  return (
    <Modal show={show} onHide={isSaving ? undefined : onHide} centered>
      <Modal.Header closeButton={!isSaving}>
        <Modal.Title>Add Opening Balance</Modal.Title>
      </Modal.Header>
      <Modal.Body className="d-flex flex-column gap-3">
        <Row className="g-3">
          <Col md={6}>
            <Form.Group controlId="opening-balance-date">
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
            <Form.Group controlId="opening-balance-time">
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

        <Form.Group controlId="opening-balance-asset">
          <Form.Label>Asset</Form.Label>
          <Form.Control
            type="text"
            value={assetId}
            disabled={isSaving}
            onChange={(event) => setAssetId(event.target.value)}
          />
        </Form.Group>

        <Form.Group controlId="opening-balance-account">
          <Form.Label>Account</Form.Label>
          <Form.Select
            value={accountChainId}
            disabled={isSaving}
            onChange={(event) => setAccountChainId(event.target.value)}
          >
            <option value="">Select an account</option>
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

        <Form.Group controlId="opening-balance-quantity">
          <Form.Label>Quantity</Form.Label>
          <Form.Control
            type="text"
            value={quantity}
            disabled={isSaving}
            onChange={(event) => setQuantity(event.target.value)}
          />
        </Form.Group>

        <Form.Group controlId="opening-balance-price">
          <Form.Label>Price Per Token</Form.Label>
          <Form.Control
            type="text"
            value={pricePerToken}
            disabled={isSaving}
            onChange={(event) => setPricePerToken(event.target.value)}
            placeholder="Optional"
          />
        </Form.Group>

        <Form.Group controlId="opening-balance-note">
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
            {validationMessage || errorMessage}
          </Alert>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button
          variant="outline-secondary"
          disabled={isSaving}
          onClick={onHide}
        >
          Cancel
        </Button>
        <Button variant="primary" disabled={isSaving} onClick={handleSubmit}>
          {isSaving ? "Saving..." : "Save opening balance"}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
