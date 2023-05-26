from datetime import datetime

from typing import cast
from typing import TypedDict

from app import state
from app.constants import VoteType

READ_PARAMS = """\
    request_id, 
    vote_user_id, 
    vote_type, 
    created_at
"""


class ScorewatchVote(TypedDict):
    request_id: int
    vote_user_id: int
    vote_type: str
    created_at: datetime


async def create(
    request_id: int,
    vote_user_id: int,
    vote_type: VoteType,
) -> ScorewatchVote:
    query = f"""\
        INSERT INTO scorewatch_votes (request_id, vote_user_id, vote_type)
        VALUES (:request_id, :vote_user_id, :vote_type)
        RETURNING {READ_PARAMS}
    """
    params = {
        "request_id": request_id,
        "vote_user_id": vote_user_id,
        "vote_type": vote_type.value,
    }
    rec = await state.write_database.fetch_one(query, params)
    return cast(ScorewatchVote, rec)


async def fetch_one(request_id: int, vote_user_id: int) -> ScorewatchVote | None:
    query = f"""\
        SELECT {READ_PARAMS} 
        FROM scorewatch_votes
        WHERE request_id = :request_id
        AND vote_user_id = :vote_user_id
    """

    params = {
        "request_id": request_id,
        "vote_user_id": vote_user_id,
    }
    rec = await state.read_database.fetch_one(query, params)

    if rec is None:
        return None

    return cast(ScorewatchVote, rec)


async def fetch_all(request_id: int, vote_type: VoteType) -> list[ScorewatchVote]:
    query = f"""\
        SELECT {READ_PARAMS} 
        FROM scorewatch_votes
        WHERE request_id = :request_id
        AND vote_type = :vote_type
    """
    params = {
        "request_id": request_id,
        "vote_type": vote_type.value,
    }
    rec = await state.read_database.fetch_all(query, params)

    return cast(list[ScorewatchVote], rec)
