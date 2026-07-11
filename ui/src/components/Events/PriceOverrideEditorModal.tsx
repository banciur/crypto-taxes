// This file is completely vibed and I didn't read it.
"use client";

import { useState } from "react";

import { Alert, Button, Col, Form, Modal, Row } from "react-bootstrap";

import { OriginId } from "@/components/OriginId";
import { BASE_CURRENCY_ASSET_ID } from "@/consts";
import {
  absDecimalString,
  divideDecimalStrings,
  formatDecimalString,
  getDecimalStringSign,
  isNonZeroDecimalString,
  multiplyDecimalStrings,
  normalizeDecimalInput,
} from "@/lib/decimalStrings";
import type {
  CreatePriceOverridePayload,
  PriceOverrideEditorContext,
} from "@/types/events";

type PriceOverrideEditorModalProps = {
  show: boolean;
  context: PriceOverrideEditorContext;
  isSaving: boolean;
  errorMessage: string | null;
  onHide: () => void;
  onSubmit: (payload: CreatePriceOverridePayload) => Promise<void>;
};

export function PriceOverrideEditorModal({
  show,
  context,
  isSaving,
  errorMessage,
  onHide,
  onSubmit,
}: PriceOverrideEditorModalProps) {
  const { eventOrigin, assetId, legQuantity } = context;
  const [rate, setRate] = useState("");
  const [totalValue, setTotalValue] = useState("");
  const [note, setNote] = useState("");
  const [validationMessage, setValidationMessage] = useState<string | null>(
    null,
  );

  // The leg quantity is only used to convert between the two inputs, and a leg may be negative
  // (a disposal), so the total value is expressed against the absolute quantity.
  const absoluteQuantity = absDecimalString(legQuantity);
  const isConvertible = isNonZeroDecimalString(absoluteQuantity);

  const handleRateChange = (value: string) => {
    setRate(value);
    const normalizedRate = normalizeDecimalInput(value);
    if (normalizedRate === null || !isConvertible) {
      setTotalValue("");
      return;
    }
    setTotalValue(multiplyDecimalStrings(normalizedRate, absoluteQuantity));
  };

  const handleTotalValueChange = (value: string) => {
    setTotalValue(value);
    const normalizedTotalValue = normalizeDecimalInput(value);
    if (normalizedTotalValue === null || !isConvertible) {
      setRate("");
      return;
    }
    setRate(divideDecimalStrings(normalizedTotalValue, absoluteQuantity));
  };

  const handleSubmit = async () => {
    const rateEur = normalizeDecimalInput(rate);
    if (rateEur === null || getDecimalStringSign(rateEur) !== 1) {
      setValidationMessage("Rate must be a positive decimal.");
      return;
    }

    setValidationMessage(null);
    const payload: CreatePriceOverridePayload = {
      eventOrigin,
      assetId,
      rateEur,
    };
    const trimmedNote = note.trim();
    if (trimmedNote) {
      payload.note = trimmedNote;
    }

    await onSubmit(payload);
  };

  return (
    <Modal show={show} onHide={isSaving ? undefined : onHide} centered>
      <Modal.Header closeButton={!isSaving}>
        <Modal.Title>Set price for {assetId}</Modal.Title>
      </Modal.Header>
      <Modal.Body className="d-flex flex-column gap-3">
        <div className="rounded border p-3">
          <div className="small fw-semibold text-uppercase text-muted">
            Corrected event
          </div>
          <div className="d-flex align-items-center gap-2">
            <span className="fw-semibold">{eventOrigin.location}</span>
            <OriginId
              originId={eventOrigin.externalId}
              place={eventOrigin.location.toLowerCase()}
              className="fw-semibold"
            />
          </div>
          <div className="small text-muted">
            Leg quantity: {formatDecimalString(legQuantity)} {assetId}
          </div>
        </div>

        <Row className="g-3">
          <Col md={6}>
            <Form.Group controlId="price-override-rate">
              <Form.Label>{`Rate (${BASE_CURRENCY_ASSET_ID} per unit)`}</Form.Label>
              <Form.Control
                type="text"
                value={rate}
                disabled={isSaving}
                onChange={(event) => handleRateChange(event.target.value)}
              />
            </Form.Group>
          </Col>
          <Col md={6}>
            <Form.Group controlId="price-override-total-value">
              <Form.Label>{`Total value (${BASE_CURRENCY_ASSET_ID})`}</Form.Label>
              <Form.Control
                type="text"
                value={totalValue}
                disabled={isSaving || !isConvertible}
                onChange={(event) => handleTotalValueChange(event.target.value)}
              />
            </Form.Group>
          </Col>
        </Row>
        <div className="small text-muted">
          {isConvertible
            ? "Editing either field recomputes the other from the leg quantity. Only the rate is saved."
            : "The leg quantity is zero, so the total value cannot be converted. Enter the rate directly."}
        </div>

        <Form.Group controlId="price-override-note">
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
          {isSaving ? "Saving..." : "Save price override"}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
