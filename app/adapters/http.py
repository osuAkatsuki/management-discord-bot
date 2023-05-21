from __future__ import annotations

from httpx import AsyncClient


class ServiceHTTP(AsyncClient):
    async def download_file(self, url: str, path: str) -> None:
        file_data = await self.get(url)

        if file_data.status_code != 200 or not file_data.content:
            return

        with open(path, "wb") as f:
            f.write(file_data.content)
