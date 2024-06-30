import io
import logging
import typing
import zipfile
from typing import TypedDict

import httpx
from PIL import Image

from app import state
from app.common import settings


beatmaps_service_http_client = httpx.AsyncClient(
    base_url=settings.APP_BEATMAPS_SERVICE_URL,
)


class Beatmap(TypedDict):
    artist: str
    title: str
    creator: str
    version: str


async def get_beatmap_background_image(
    beatmap_id: int,
    beatmapset_id: int,
) -> Image.Image | None:
    """Gets a beatmap's background image by any means."""
    background_image = await _get_beatmap_background_image_online(
        beatmap_id,
        beatmapset_id,
    )

    if background_image is None:
        background_image = await _get_beatmap_background_image_io(
            beatmap_id,
            beatmapset_id,
        )

    if background_image is None:
        return None

    return background_image


async def get_osu_file_contents(beatmap_id: int) -> bytes | None:
    """Fetch the .osu file content for a beatmap."""
    try:
        response = await state.http_client.get(
            f"/api/osu-api/v1/osu-files/{beatmap_id}",
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.read()
    except Exception:
        logging.warning(
            "Failed to fetch .osu file contents from beatmaps-service",
            extra={"beatmap_id": beatmap_id},
            exc_info=True,
        )
        return None


async def get_osz2_file_contents(beatmapset_id: int) -> bytes | None:
    """Fetch the .osz2 file content for a beatmapset."""
    try:
        response = await beatmaps_service_http_client.get(
            f"/public/api/d/{beatmapset_id}",
        )
        response.raise_for_status()
        return response.read()
    except Exception:
        logging.warning(
            "Failed to fetch .osz2 file contents from beatmaps-service",
            extra={"beatmapset_id": beatmapset_id},
            exc_info=True,
        )
        return None


async def _get_beatmap_background_image_online(
    beatmap_id: int,
    _: int,
) -> Image.Image | None:
    response = await state.http_client.get(
        f"https://api.osu.direct/media/background/{beatmap_id}",
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
    beatmap_id: int,
    beatmapset_id: int,
) -> Image.Image | None:
    """Gets a beatmap's background image by any means."""
    beatmap = await get_osu_file_contents(beatmap_id)
    if beatmap is None:
        logging.warning(
            "Could not retrieve .osu file contents from beatmaps-service",
            extra={"beatmap_id": beatmap_id},
        )
        return None

    background_filename = find_beatmap_background_filename(beatmap)
    if background_filename is None:
        logging.warning(
            "Could not find background image filename in beatmap .osu file",
            extra={"beatmap_id": beatmap_id},
        )
        return None

    data = await get_osz2_file_contents(beatmapset_id)
    if data is None:
        logging.warning(
            "Could not retrieve .osz2 file contents from beatmaps-service",
            extra={"beatmapset_id": beatmapset_id},
        )
        return None

    with io.BytesIO(data) as zip_file:
        with zipfile.ZipFile(zip_file) as zip_ref:
            for filename in zip_ref.namelist():
                if filename == background_filename:
                    break
            else:
                logging.warning(
                    "Could not find desired background image in beatmapset .osz2 file",
                    extra={
                        "beatmapset_id": beatmapset_id,
                        "background_filename": background_filename,
                    },
                )
                return None

            with zip_ref.open(filename) as image_file:
                image = Image.open(image_file)
                image.load()
                return image


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

    return typing.cast(Beatmap, beatmap)


def find_beatmap_background_filename(osu_file_bytes: bytes) -> str | None:
    lines = osu_file_bytes.decode("utf-8-sig").splitlines()

    for line in lines:
        if line.startswith("0,0,"):
            background_path = line.split(",")[2].strip().strip('"')
            return background_path

    return None
