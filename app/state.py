from app.adapters.database import Database
from app.adapters.http import AsyncClient
from app.adapters.webdriver import WebDriver

read_database: Database
write_database: Database
http_client: AsyncClient
webdriver: WebDriver
