import io
import logging
from typing import TypedDict
import typing
import zipfile
from app import state
from app.adapters import aws_s3
from app.adapters import osu_api_v1
from PIL import Image
from app.adapters.beatmaps.mirrors import (
    BeatmapMirror,
    CatboyBestMirror,
    OsuDirectMirror,
)


# New template doesn't use max_combo so we can silently get rid of slider package
class Beatmap(TypedDict):
    artist: str
    title: str
    creator: str
    version: str
    max_combo: int


BEATMAP_MIRRORS: list[BeatmapMirror] = [
    OsuDirectMirror(),
    CatboyBestMirror(),
]


async def get_beatmap(beatmap_id: int) -> bytes | None:
    osu_file_contents = await aws_s3.get_object_data(f"/beatmaps/{beatmap_id}.osu")
    if not osu_file_contents:
        osu_file_contents = await osu_api_v1.get_osu_file_contents(beatmap_id)

    if not osu_file_contents:
        return None

    # NOTE: intentionally not saving to s3 here, because we don't want to
    # disrupt other online systems with potentially newer data.
    return osu_file_contents


async def get_beatmap_background_image(
    beatmap_id: int, beatmapset_id: int
) -> Image.Image | None:
    """Gets a beatmap's background image by any means."""
    background_image = await _get_beatmap_background_image_online(
        beatmap_id, beatmapset_id
    )

    if background_image is None:
        background_image = await _get_beatmap_background_image_io(
            beatmap_id, beatmapset_id
        )

    if background_image is None:
        return None

    return background_image


async def _get_beatmap_background_image_online(
    beatmap_id: int, _: int
) -> Image.Image | None:
    osu_background_url = f"https://api.osu.direct/media/background/{beatmap_id}"
    response = await state.http_client.get(
        osu_background_url,
        headers={"User-Agent": "akatsuki/management-bot"},
    )
    response.raise_for_status()

    background_data = response.read()
    if b"beatmap not found!" in background_data:
        logging.warning(
            "Failed to find beatmap background image on osu.direct",
            extra={"beatmap_id": beatmap_id},
        )
        return None

    with io.BytesIO(background_data) as image_file:
        image = Image.open(image_file)
        image.load()

    return image


async def _get_beatmap_background_image_io(
    beatmap_id: int, beatmapset_id: int
) -> Image.Image | None:
    """Gets a beatmap's background image by any means."""
    beatmap = await get_beatmap(beatmap_id)
    if beatmap is None:
        return None

    background_filename = find_beatmap_background_filename(beatmap)
    if background_filename is None:
        return None

    for mirror in BEATMAP_MIRRORS:
        data = await mirror.fetch_beatmap_zip_data(beatmapset_id)
        if data is None:  # try next mirror
            continue

        with io.BytesIO(data) as zip_file:
            with zipfile.ZipFile(zip_file) as zip_ref:
                for file_name in zip_ref.namelist():
                    if file_name == background_filename:
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


def parse_beatmap_metadata(osu_file_bytes: bytes) -> Beatmap:
    lines = osu_file_bytes.decode().splitlines()
    beatmap = {}
    for line in lines[1:]:
        if line.startswith("Artist:"):
            beatmap["artist"] = line.split(":")[1].strip()
        elif line.startswith("Title:"):
            beatmap["title"] = line.split(":")[1].strip()
        elif line.startswith("Creator:"):
            beatmap["creator"] = line.split(":")[1].strip()
        elif line.startswith("Version:"):
            beatmap["version"] = line.split(":")[1].strip()

    beatmap["max_combo"] = 0
    return typing.cast(Beatmap, beatmap)


def find_beatmap_background_filename(osu_file_bytes: bytes) -> str | None:
    lines = osu_file_bytes.decode("utf-8-sig").splitlines()

    for line in lines:
        if line.startswith("0,0,"):
            background_path = line.split(",")[2].strip().strip('"')
            return background_path

    return None
