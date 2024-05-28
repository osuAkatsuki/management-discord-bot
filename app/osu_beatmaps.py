import io
import logging
import zipfile
import slider
from app.adapters import aws_s3
from app.adapters.beatmaps.mirrors import (
    BeatmapMirror,
    CatboyBestMirror,
    ChimuMoeMirror,
    OsuDirectMirror,
)


BEATMAP_MIRRORS: list[BeatmapMirror] = [
    ChimuMoeMirror(),
    OsuDirectMirror(),
    CatboyBestMirror(),
]


async def get_beatmap(beatmap_id: int) -> slider.Beatmap | None:
    beatmap_data = await aws_s3.get_object_data(f"/beatmaps/{beatmap_id}.osu")
    if not beatmap_data:
        return None

    try:
        return slider.Beatmap.parse(beatmap_data)
    except Exception:
        logging.warning(
            "Failed to parse osu! beatmap file data",
            exc_info=True,
        )
        return None


async def get_beatmap_background_image_data(beatmapset_id: int) -> bytes | None:
    """Gets a beatmap's background image file data by any means."""
    for mirror in BEATMAP_MIRRORS:
        data = await mirror.fetch_beatmap_zip_data(beatmapset_id)
        if data is None:  # try next mirror
            continue

        with io.BytesIO(data) as zip_file:
            with zipfile.ZipFile(zip_file) as zip_ref:
                for file_name in zip_ref.namelist():
                    if file_name.endswith(".jpg"):
                        break
                else:  # try next mirror
                    continue

                with zip_ref.open(file_name) as image_file:
                    return image_file.read()

    logging.warning(
        "Could not find a beatmap by set id on any of our mirrors",
        extra={"beatmapset_id": beatmapset_id},
    )
    return None
