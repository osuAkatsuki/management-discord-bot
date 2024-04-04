from httpx import AsyncClient


class HTTPClient(AsyncClient):
    async def download_file(self, url: str, path: str, is_replay: bool = False) -> None:
        headers = {"user-agent": "akatsuki/management-bot"}
        file_data = await self.get(
            url,
            headers=headers,
            timeout=60,
            follow_redirects=True,
        )  # temporary fix for random timeouts

        if file_data.status_code != 200 or not file_data.content:
            return

        if is_replay and len(file_data.content) < 100:
            return

        with open(path, "wb") as f:
            f.write(file_data.content)
