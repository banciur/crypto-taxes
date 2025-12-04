from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from domain.ledger import DisposalId, LotId


class TaxEventKind(StrEnum):
    DISPOSAL = "DISPOSAL"
    REWARD = "REWARD"


@dataclass
class TaxEvent:
    source_id: DisposalId | LotId
    kind: TaxEventKind
    taxable_gain: Decimal
