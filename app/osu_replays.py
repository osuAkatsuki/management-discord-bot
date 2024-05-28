import io
import logging
from app.adapters import aws_s3
import aiosu


class Replay(aiosu.models.replay.ReplayFile):
    raw_replay_data: bytes


async def get_replay(score_id: int) -> Replay | None:
    osu_replay_data = await aws_s3.get_object_data(f"/replays/{score_id}.osr")
    if not osu_replay_data:
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
