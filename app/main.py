#!/usr/bin/env python3
import base64
import textwrap
from typing import Literal
from urllib import parse

import discord
import ssl
import sys
import os
import aiosu

from aiosu.models.mods import Mod
from discord.ext import commands
from discord import app_commands

# add .. to path
srv_root = os.path.join(os.path.dirname(__file__), "..")

sys.path.append(srv_root)

from app import settings, views, scorewatch
from app.adapters import database
from app.adapters import http
from app.adapters import webdriver
from app import state
from app.constants import Status
from app.repositories import scores, sw_requests


dirs = (
    settings.DATA_DIR,
    os.path.join(settings.DATA_DIR, "beatmap"),
    os.path.join(settings.DATA_DIR, "replay"),
    os.path.join(settings.DATA_DIR, "finals"),
    os.path.join(settings.DATA_DIR, "finals", "backgrounds"),
    os.path.join(settings.DATA_DIR, "finals", "html"),
    os.path.join(settings.DATA_DIR, "finals", "thumbnails"),
)

SW_WHITELIST = [
    291927822635761665,  # lenforiee
    285190493703503872,  # cmyui
    153954447247147018,  # rapha
]


def check_folder(path: str) -> None:
    if not os.path.exists(path):
        os.mkdir(path)


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            help_command=None,
            *args,
            **kwargs,
        )


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

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

    state.http_client = http.HTTPClient()
    state.webdriver = webdriver.WebDriver()

    for dir in dirs:
        check_folder(dir)

    # Load views so the existing one will still work.
    bot.add_view(views.ReportView(bot))
    for sw_request in await sw_requests.fetch_all():
        if sw_request["request_status"] in Status.resolved_statuses():
            continue  # No point in adding already resolved requests perhaps threads are even gone by now.

        bot.add_view(
            views.ScorewatchButtonView(sw_request["score_id"], bot),
            message_id=sw_request["thread_message_id"],
        )

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

        bot_id = bot.user.id  # type: ignore
        embed = discord.Embed(
            title="Reporting a Player",
            description="\n\n".join(
                (
                    f"To report a player, we now use the <@{bot_id}> bot.",
                    (  # One line text
                        "In order to use it, simply click the button below and provide the "
                        "URL to the player you are reporting, as well as the reason for your report. "
                        "The displayed form should guide you through all the necessary fields."
                    ),
                )
            ),
        )
        await channel.send(view=view, embed=embed)  # type: ignore

    else:
        await interaction.followup.send("Invalid embed type!", ephemeral=True)
        return

    await interaction.followup.send("Embed sent!", ephemeral=True)


@bot.tree.command(
    name="request",
    description="Request to upload a replay!",
)
@app_commands.describe(replay_url="Akatsuki replay URL")
async def request(
    interaction: discord.Interaction,
    replay_url: str,
) -> None:
    channel = await bot.fetch_channel(settings.ADMIN_SCOREWATCH_CHANNEL_ID)
    role = interaction.guild.get_role(settings.AKATSUKI_SCOREWATCH_ROLE_ID)  # type: ignore

    if not role:
        return  # ?????

    await interaction.response.defer(ephemeral=True)

    if interaction.channel_id != settings.SCOREWATCH_CHANNEL_ID:
        await interaction.followup.send(
            f"Please use this command in <#{settings.SCOREWATCH_CHANNEL_ID}> to request a replay!",
            ephemeral=True,
        )
        return

    parsed_url = parse.urlparse(replay_url)
    if parsed_url.hostname not in ("akatsuki.pw", "akatsuki.gg"):
        await interaction.followup.send(
            "This is not a valid Akatsuki replay URL!\n"
            "Valid syntax: `https://akatsuki.gg/web/replays/XXXXXXXX`",
            ephemeral=True,
        )
        return

    score_id = parsed_url.path[13:]

    if not score_id.isnumeric():
        await interaction.followup.send(
            "This is not a valid Akatsuki replay URL!\n"
            "Valid syntax: `https://akatsuki.gg/web/replays/XXXXXXXX`",
            ephemeral=True,
        )
        return

    replay_path = os.path.join(settings.DATA_DIR, "replay", f"{score_id}.osr")
    await state.http_client.download_file(replay_url, replay_path, is_replay=True)

    if not os.path.exists(replay_path):
        await interaction.followup.send(
            "This replay does not exist!",
            ephemeral=True,
        )
        return

    request_data = await sw_requests.fetch_one(int(score_id))
    if request_data:
        await interaction.followup.send(
            f"This score has been requested on <t:{int(request_data['created_at'].timestamp())}>, "
            f"current status: **{request_data['request_status']}**!",
            ephemeral=True,
        )
        return

    replay_file = aiosu.utils.replay.parse_path(replay_path)

    relax = 0
    relax_text = "VN"
    if replay_file.mods & Mod.Relax:
        relax = 1
        relax_text = "RX"
    elif replay_file.mods & Mod.Autopilot:
        relax = 2
        relax_text = "AP"

    score_data = await scores.fetch_one(int(score_id), relax)
    if not score_data:
        await interaction.followup.send(
            "Could not find information about this score!",
            ephemeral=True,
        )
        return

    thread_starter_message_content = textwrap.dedent(
        f"""\
        {interaction.user.mention} requested a replay upload for ID [{score_id}](<https://akatsuki.gg/web/replays/{score_id}>)

        Player: [{score_data['user']['username']}](<https://akatsuki.gg/u/{score_data['user']['id']}>)
        Map: [{score_data['beatmap']['song_name']}](<https://akatsuki.gg/b/{score_data['beatmap']['beatmap_id']}>)

        🔽 for specific details see the thread 🔽
        """,
    )
    thread_starter_message = await channel.send(thread_starter_message_content)  # type: ignore
    status = Status.PENDING

    await interaction.followup.send(
        f"Request successfully sent, current status: **{status}**!",
        ephemeral=True,
    )

    thread_starter_message.guild = interaction.guild
    thread = await thread_starter_message.create_thread(
        name=f"[{relax_text}] {score_data['user']['username']} - {score_data['beatmap']['song_name']}",
    )

    users_mentions = set(map(lambda x: x.mention, role.members))
    thread_embed = await thread.send(
        content=textwrap.dedent(
            f"""\
                Hey, <@&{settings.AKATSUKI_SCOREWATCH_ROLE_ID}>! A new upload request has been submitted.

                **Remember you can only vote once!**

                **Vote with the reactions below!**
                **0**/{len(users_mentions)} voted!
                List of people left to vote:
                {', '.join(users_mentions)}
            """,
        ),
        file=discord.File(replay_path),
        view=views.ScorewatchButtonView(int(score_id), bot),
    )

    request_data = await sw_requests.create(
        interaction.user.id,
        int(score_id),
        relax,
        status.value,
        thread_embed.id,
        thread.id,
    )

    embed = await scorewatch.format_request_embed(bot, score_data, request_data, status)

    if isinstance(embed, str):
        await interaction.followup.send(embed, ephemeral=True)
        return

    await thread_embed.edit(embed=embed)


@bot.tree.command(
    name="regenerate",
    description="Regenerate a youtube thumbnail, title and description!",
)
@app_commands.describe(
    score_id="Score ID",
    username="(Optional) Username of the player",
    artist="(Optional) Artist of the map",
    title="(Optional) Title of the map",
    difficulty_name="(Optional) Difficulty name of the map",
    detail_text="(Optional) Detail text in bottom right corner (Thumbnail)",
    detail_colour="(Optional) Detail colour (hex) for misc text (Thumbnail)",
)
async def regenerate(
    interaction: discord.Interaction,
    score_id: str,
    username: str = "",
    artist: str = "",
    title: str = "",
    difficulty_name: str = "",
    detail_text: str = "",
    detail_colour: str = "",
) -> None:
    await interaction.response.defer()

    role = interaction.guild.get_role(settings.AKATSUKI_SCOREWATCH_ROLE_ID)  # type: ignore
    if not role:
        return  # ???????

    if not role in interaction.user.roles and not interaction.user.id in SW_WHITELIST:  # type: ignore
        await interaction.followup.send(
            "You don't have permission to run this command!",
            ephemeral=True,
        )
        return

    if not score_id.isnumeric():
        await interaction.followup.send(
            "You must provide a valid score ID!",
            ephemeral=True,
        )
        return

    request_data = await sw_requests.fetch_one(int(score_id))
    if not request_data:
        await interaction.followup.send(
            "Couldn't find this request!",
            ephemeral=True,
        )
        return

    if request_data["request_status"] != Status.ACCEPTED.value:
        await interaction.followup.send(
            "This request is not accepted!",
            ephemeral=True,
        )
        return

    score_data = await scores.fetch_one(int(score_id), request_data["score_relax"])
    if not score_data:
        await interaction.followup.send(
            "Couldn't find this score!",
            ephemeral=True,
        )
        return

    metadata = await scorewatch.generate_normal_metadata(
        score_data,
        username,
        artist,
        title,
        difficulty_name,
        detail_text,
        detail_colour,
    )

    if isinstance(metadata, str):
        await interaction.followup.send(metadata)
        return

    await interaction.followup.send(
        "\n".join(
            (
                "**Title:**",
                f"```{metadata['title']}```",
                "",
                "**Description:**",
                f"```{metadata['description']}```",
                "",
                "**Thumbnail:**",
            ),
        ),
        file=discord.File(
            metadata["file"],
        ),
    )


if __name__ == "__main__":
    bot.run(settings.DISCORD_TOKEN)
