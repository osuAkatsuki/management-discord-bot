#!/usr/bin/env python3
import base64
import os
import ssl
import sys

import discord
from discord.ext import commands

# add .. to path
srv_root = os.path.join(os.path.dirname(__file__), "..")

sys.path.append(srv_root)

from app import settings
from app.adapters import database
from app.adapters import http
from app.adapters import webdriver
from app import state


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            help_command=None,
            *args,
            **kwargs,
        )

    async def setup_hook(self) -> None:
        ...


intents = discord.Intents.default()
intents.message_content = True

bot = Bot(intents=intents)


@bot.event
async def on_ready() -> None:
    state.read_database = database.Database(
        database.dsn(
            scheme="postgresql",
            user=settings.READ_DB_USER,
            password=settings.READ_DB_PASS,
            host=settings.READ_DB_HOST,
            port=settings.READ_DB_PORT,
            database=settings.READ_DB_NAME,
        ),
        db_ssl=(
            ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH,
                cadata=base64.b64decode(settings.READ_DB_CA_CERTIFICATE).decode(),
            )
            if settings.READ_DB_USE_SSL
            else False
        ),
        min_pool_size=settings.DB_POOL_MIN_SIZE,
        max_pool_size=settings.DB_POOL_MAX_SIZE,
    )
    await state.read_database.connect()

    state.write_database = database.Database(
        database.dsn(
            scheme="postgresql",
            user=settings.WRITE_DB_USER,
            password=settings.WRITE_DB_PASS,
            host=settings.WRITE_DB_HOST,
            port=settings.WRITE_DB_PORT,
            database=settings.WRITE_DB_NAME,
        ),
        db_ssl=(
            ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH,
                cadata=base64.b64decode(settings.WRITE_DB_CA_CERTIFICATE).decode(),
            )
            if settings.WRITE_DB_USE_SSL
            else False
        ),
        min_pool_size=settings.DB_POOL_MIN_SIZE,
        max_pool_size=settings.DB_POOL_MAX_SIZE,
    )
    await state.write_database.connect()

    state.http_client = http.AsyncClient()
    state.webdriver = webdriver.WebDriver()

    await bot.tree.sync()


if __name__ == "__main__":
    bot.run(settings.DISCORD_TOKEN)
