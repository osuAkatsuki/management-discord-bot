import logging

from app import state


async def get_osu_file_contents(beatmap_id: int) -> bytes | None:
    """Fetch the .osu file content for a beatmap."""
    try:
        response = await state.http_client.get(
            f"https://old.ppy.sh/osu/{beatmap_id}",
        )
        response.raise_for_status()
        return response.read()
    except Exception:
        logging.warning(
            "Failed to fetch beatmap from osu.ppy.sh",
            exc_info=True,
        )
        return None
