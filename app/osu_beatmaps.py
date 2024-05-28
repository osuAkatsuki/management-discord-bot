import io
import logging
from typing_extensions import override
import zipfile
import slider
from app.adapters import aws_s3
from app.adapters import osu_api_v1
from PIL import Image
from app.adapters.beatmaps.mirrors import (
    BeatmapMirror,
    CatboyBestMirror,
    ChimuMoeMirror,
    OsuDirectMirror,
)


class Beatmap(slider.Beatmap):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._raw_file_data: bytes = b""

    @override
    @classmethod
    def parse(cls, data: bytes) -> "Beatmap":
        obj = super().parse(data)
        obj._raw_file_data = data
        return obj


BEATMAP_MIRRORS: list[BeatmapMirror] = [
    ChimuMoeMirror(),
    OsuDirectMirror(),
    CatboyBestMirror(),
]


async def get_beatmap(beatmap_id: int) -> Beatmap | None:
    osu_file_contents = await aws_s3.get_object_data(f"/beatmaps/{beatmap_id}.osu")
    if not osu_file_contents:
        return None

    osu_file_contents = await osu_api_v1.get_osu_file_contents(beatmap_id)
    if not osu_file_contents:
        return None

    # NOTE: intentionally not saving to s3 here, because we don't want to
    # disrupt other online systems with potentially newer data.

    try:
        return Beatmap.parse(osu_file_contents)
    except Exception:
        logging.warning(
            "Failed to parse osu! beatmap file data",
            exc_info=True,
        )
        return None


async def get_beatmap_background_image(beatmapset_id: int) -> Image.Image | None:
    """Gets a beatmap's background image by any means."""
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
                    image = Image.open(image_file)
                    image.load()
                    return image

    logging.warning(
        "Could not find a beatmap by set id on any of our mirrors",
        extra={"beatmapset_id": beatmapset_id},
    )
    return None
