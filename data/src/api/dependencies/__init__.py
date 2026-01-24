from typing import Generator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.sessionmaker() as session:
        yield session
