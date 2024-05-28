import io
import logging

import aiosu


def read_osu_replay_file_data(
    replay_data: bytes,
) -> aiosu.models.files.ReplayFile | None:
    try:
        with io.BytesIO(replay_data) as replay_file:
            return aiosu.utils.replay.parse_file(replay_file)
    except Exception:
        logging.warning(
            "Failed to parse osu! replay file data",
            exc_info=True,
        )
        return None
