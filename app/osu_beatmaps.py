import logging
import typing

import httpx

from app.common import settings


beatmaps_service_http_client = httpx.AsyncClient(
    base_url=settings.APP_BEATMAPS_SERVICE_URL,
)


class BeatmapMetadata(typing.TypedDict):
    artist: str
    title: str
    creator: str
    version: str


async def get_osu_file_contents(beatmap_id: int) -> bytes | None:
    """Fetch the .osu file content for a beatmap."""
    try:
        response = await beatmaps_service_http_client.get(
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
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.read()
    except Exception:
        logging.warning(
            "Failed to fetch .osz2 file contents from beatmaps-service",
            extra={"beatmapset_id": beatmapset_id},
            exc_info=True,
        )
        return None


async def get_beatmap_background_image_contents(beatmap_id: int) -> bytes | None:
    try:
        response = await beatmaps_service_http_client.get(
            f"/api/osu-assets/backgrounds/{beatmap_id}",
        )
        if response.status_code == 404:
            logging.warning(
                "Failed to retrieve beatmap background image from beatmaps-service",
                extra={"beatmap_id": beatmap_id},
            )
            return None
        response.raise_for_status()
        return response.read()
    except Exception:
        logging.warning(
            "Failed to retrieve beatmap background image from beatmaps-service",
            extra={"beatmap_id": beatmap_id},
        )
        return None


def parse_beatmap_metadata(osu_file_bytes: bytes) -> BeatmapMetadata:
    lines = osu_file_bytes.decode().splitlines()
    beatmap: dict[str, str] = {}
    for line in lines[1:]:
        if line.startswith("Artist:"):
            beatmap["artist"] = line.split(":")[1].strip()
        elif line.startswith("Title:"):
            beatmap["title"] = line.split(":")[1].strip()
        elif line.startswith("Creator:"):
            beatmap["creator"] = line.split(":")[1].strip()
        elif line.startswith("Version:"):
            beatmap["version"] = line.split(":")[1].strip()

    return typing.cast(BeatmapMetadata, beatmap)
