from datetime import datetime
from typing import cast
from typing import TypedDict

from app import state
from app.constants import Status

READ_PARAMS = """\
    request_id,
    requested_by,
    score_id,
    score_relax,
    request_status,
    thread_message_id,
    thread_id,
    created_at,
    resolved_at
"""


class ScorewatchRequest(TypedDict):
    request_id: int
    requested_by: int
    score_id: int
    score_relax: int
    request_status: Status
    thread_message_id: int
    thread_id: int
    created_at: datetime
    resolved_at: datetime


async def create(
    requested_by: int,
    score_id: int,
    score_relax: int,
    request_status: str,
    thread_message_id: int,
    thread_id: int,
) -> ScorewatchRequest:
    query = f"""\
        INSERT INTO scorewatch_requests
            (requested_by, score_id, score_relax, request_status, thread_message_id, thread_id)
        VALUES
            (:requested_by, :score_id, :score_relax, :request_status, :thread_message_id, :thread_id)
        RETURNING {READ_PARAMS}
    """
    params = {
        "requested_by": requested_by,
        "score_id": score_id,
        "score_relax": score_relax,
        "request_status": request_status,
        "thread_message_id": thread_message_id,
        "thread_id": thread_id,
    }
    rec = await state.write_database.fetch_one(query, params)
    return cast(ScorewatchRequest, rec)


async def partial_update(
    score_id: int,
    request_status: str | None = None,
    resolved_at: datetime | None = None,
) -> ScorewatchRequest | None:
    query = f"""\
        UPDATE scorewatch_requests
        SET request_status = COALESCE(:request_status, request_status),
            resolved_at = COALESCE(:resolved_at, resolved_at)
        WHERE score_id = :score_id
        RETURNING {READ_PARAMS}
    """
    params = {
        "score_id": score_id,
        "request_status": request_status,
        "resolved_at": resolved_at,
    }
    rec = await state.write_database.fetch_one(query, params)
    return cast(ScorewatchRequest, rec) if rec is not None else None


async def fetch_one(score_id: int) -> ScorewatchRequest | None:
    query = f"""\
        SELECT {READ_PARAMS}
        FROM scorewatch_requests
        WHERE score_id = :score_id
    """

    params = {"score_id": score_id}
    rec = await state.read_database.fetch_one(query, params)

    if rec is None:
        return None

    return cast(ScorewatchRequest, rec)


async def fetch_all() -> list[ScorewatchRequest]:
    query = f"""\
        SELECT {READ_PARAMS}
        FROM scorewatch_requests
    """

    rec = await state.read_database.fetch_all(query)

    return cast(list[ScorewatchRequest], rec)
