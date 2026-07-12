from typing import Annotated

from fastapi import Query
from pydantic import StringConstraints

from domain.ledger import AssetId

# The optional asset a lane endpoint is filtered by.
AssetFilterQuery = Annotated[AssetId | None, Query(min_length=1), StringConstraints(strip_whitespace=True)]
