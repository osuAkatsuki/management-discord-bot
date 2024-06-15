import io
import logging

import aiosu
from aiosu.models.files import ReplayFile

from app.common import settings
from app import state


class Replay(ReplayFile):
    raw_replay_data: bytes


async def get_replay(score_id: int) -> Replay | None:
    response = await state.http_client.get(
        f"{settings.APP_SCORE_SERVICE_URL}/replays/{score_id}",
    )
    response.raise_for_status()
    osu_replay_data = response.read()

    if not osu_replay_data or osu_replay_data == b"Score not found!":
        logging.warning("Failed to find osu! replay file data")
        return

    try:
        with io.BytesIO(osu_replay_data) as replay_file:
            aiosu_replay = aiosu.utils.replay.parse_file(replay_file)

        return Replay(
            **aiosu_replay.model_dump(),
            raw_replay_data=osu_replay_data,
        )
    except Exception:
        logging.warning(
            "Failed to parse osu! replay file data",
            exc_info=True,
        )
        return None
