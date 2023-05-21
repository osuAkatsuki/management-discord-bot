#!/usr/bin/env python3
from __future__ import annotations
from typing import Literal
from urllib import parse

import discord
import sys
import os

from discord.ext import commands

# add .. to path
srv_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(srv_root)

from app import settings, views
from app.adapters import database
from app.adapters import http
from app.adapters import webdriver
from app import state
from app.repositories import users


dirs = (
    settings.DATA_DIR,
    os.path.join(settings.DATA_DIR, "beatmap"),
    os.path.join(settings.DATA_DIR, "replay"),
    os.path.join(settings.DATA_DIR, "finals"),
    os.path.join(settings.DATA_DIR, "finals", "backgrounds"),
    os.path.join(settings.DATA_DIR, "finals", "html"),
    os.path.join(settings.DATA_DIR, "finals", "thumbnails"),
)

def check_folder(path: str) -> None:
    if not os.path.exists(path):
        os.mkdir(path)


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            help_command=None,
            *args,
            **kwargs
        )

    async def setup_hook(self) -> None:
        self.add_view(views.ReportView(self))


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
        db_ssl=settings.READ_DB_USE_SSL,
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
        db_ssl=settings.WRITE_DB_USE_SSL,
        min_pool_size=settings.DB_POOL_MIN_SIZE,
        max_pool_size=settings.DB_POOL_MAX_SIZE,
    )
    await state.write_database.connect()

    state.http_client = http.AsyncClient()
    state.webdriver = webdriver.WebDriver()

    for dir in dirs:
        check_folder(dir)

    await bot.tree.sync()

@bot.tree.command(
    name="genembed",
    description="Generate an embed for a channel!",
)
async def genembed(
    interaction: discord.Interaction,
    embed_type: Literal["report"],
    channel_id: str,
) -> None:
    
    # check if the user is an admin.
    if not interaction.user.guild_permissions.administrator:  # type: ignore
        await interaction.response.send_message(
            "You must be an administrator to use this command!",
            ephemeral=True,
        )
        return

    if not channel_id.isnumeric():
        await interaction.response.send_message(
            "You must provide a valid channel ID!",
            ephemeral=True,
        )
        return
    
    await interaction.response.defer(ephemeral=True)

    channel = bot.get_channel(int(channel_id))
    if not channel:
        await interaction.response.send_message(
            "Channel not found!",
            ephemeral=True,
        )
        return

    if embed_type == "report":
        view = views.ReportView(bot)

        bot_id = bot.user.id # type: ignore
        embed = discord.Embed(
            title="Reporting a Player",
            description="\n\n".join((
                f"To report a player, we now use the <@{bot_id}> bot.",
                ( # One line text
                    "In order to use it, simply click the button below and provide the "
                    "URL to the player you are reporting, as well as the reason for your report. "
                    "The displayed form should guide you through all the necessary fields."
                ),
            )),
        )
        await channel.send(view=view, embed=embed) # type: ignore

    else:
        await interaction.followup.send("Invalid embed type!", ephemeral=True)
        return
    
    await interaction.followup.send("Embed sent!", ephemeral=True)




if __name__ == "__main__":
    bot.run(settings.DISCORD_TOKEN)
