from __future__ import annotations

from typing import TYPE_CHECKING

from httpx import AsyncClient

if TYPE_CHECKING:
    from app.adapters.database import Database
    from app.adapters.webdriver import WebDriver
    from types_aiobotocore_s3.client import S3Client

read_database: Database
write_database: Database
http_client: AsyncClient
webdriver: WebDriver
s3_client: S3Client
