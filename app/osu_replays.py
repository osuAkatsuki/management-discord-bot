import io
import logging
import aiosu

from app import state
from aiosu.models.files import ReplayFile


class Replay(ReplayFile):
    raw_replay_data: bytes


async def get_replay(score_id: int) -> Replay | None:
    response = await state.http_client.get(
        f"https://akatsuki.gg/web/replays/{score_id}",
        headers={"User-Agent": "akatsuki/management-bot"},
    )
    response.raise_for_status()
    osu_replay_data = response.read()

    if not osu_replay_data or osu_replay_data == b"Score not found!":
        logging.warning(
            "Failed to find osu! replay file data on S3",
            exc_info=True,
        )
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