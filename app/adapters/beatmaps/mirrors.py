import logging
from abc import ABC
from abc import abstractmethod
from typing import ClassVar

from app import state


class BeatmapMirror(ABC):
    base_url: ClassVar[str]

    @abstractmethod
    async def fetch_beatmap_zip_data(self, beatmapset_id: int) -> bytes | None:
        """Fetch a beatmap's .osz2 file content from a beatmap mirror."""
        pass


class OsuDirectMirror(BeatmapMirror):
    base_url = "https://api.osu.direct"

    async def fetch_beatmap_zip_data(self, beatmapset_id: int) -> bytes | None:
        try:
            response = await state.http_client.get(
                f"{self.base_url}/d/{beatmapset_id}",
            )
            response.raise_for_status()
            return response.read()
        except Exception:
            logging.warning(
                "Failed to fetch beatmap from osu!direct",
                exc_info=True,
            )
            return None


class CatboyBestMirror(BeatmapMirror):
    base_url = "https://catboy.best"

    async def fetch_beatmap_zip_data(self, beatmapset_id: int) -> bytes | None:
        try:
            response = await state.http_client.get(
                f"{self.base_url}/d/{beatmapset_id}",
            )
            response.raise_for_status()
            return response.read()
        except Exception:
            logging.warning(
                "Failed to fetch beatmap from catboy.best",
                exc_info=True,
            )
            return None
