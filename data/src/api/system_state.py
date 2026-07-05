from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_system_state_repository
from db.system_state import SystemStateRepository
from domain.system_state import SystemState

router = APIRouter()


@router.get("/system-state", response_model=SystemState)
def get_system_state(
    repo: Annotated[SystemStateRepository, Depends(get_system_state_repository)],
) -> SystemState:
    return repo.get()
