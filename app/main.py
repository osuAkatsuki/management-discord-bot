#!/usr/bin/env python3
import base64
import io
import os
import ssl
import sys
import textwrap
from typing import Any
from typing import Literal
from urllib import parse

import aiobotocore.session
import discord
import httpx
from aiosu.models.mods import Mod
from discord import app_commands
from discord.ext import commands

# add .. to path
srv_root = os.path.join(os.path.dirname(__file__), "..")

sys.path.append(srv_root)

from app import osu_replays, logger
from app.common import views
from app.usecases import scorewatch
from app.common import settings
from app.adapters import database
from app.adapters import webdriver
from app import state
from app.constants import Status
from app.repositories import scores, sw_requests


SW_WHITELIST = [
    291927822635761665,  # lenforiee
    285190493703503872,  # cmyui
    272111921610752003,  # tsunyoku
]


class Bot(commands.Bot):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            commands.when_mentioned_or("!"),
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

    state.http_client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": "akatsuki/management-bot"},
    )
    state.webdriver = webdriver.WebDriver()

    aws_session = aiobotocore.session.get_session()
    s3_client = aws_session.create_client(
        service_name="s3",
        region_name=settings.AWS_S3_REGION_NAME,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_S3_SECRET_ACCESS_KEY,
    )
    state.s3_client = await s3_client.__aenter__()

    # Load views so the existing one will still work.
    bot.add_view(views.ReportView(bot))
    for sw_request in await sw_requests.fetch_all():
        if sw_request["request_status"].value in Status.resolved_statuses():
            continue  # No point in adding already resolved requests perhaps threads are even gone by now.

        bot.add_view(
            views.ScorewatchButtonView(sw_request["score_id"], bot),
            message_id=sw_request["thread_message_id"],
        )

    await bot.tree.sync()


@bot.tree.command(
    name="genembed",
    description="Generate an interactive embed for a specific channel!",
)
async def genembed(
    interaction: discord.Interaction,
    embed_type: Literal["report"],
    channel_id: str,
) -> None:
    # check if the user is an admin.

    assert isinstance(interaction.user, discord.Member)
    assert bot.user is not None

    if not interaction.user.guild_permissions.administrator:
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
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message(
            "Channel not found!",
            ephemeral=True,
        )
        return

    if embed_type == "report":
        view = views.ReportView(bot)

        bot_id = bot.user.id
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
                ),
            ),
        )
        await channel.send(view=view, embed=embed)

    else:
        await interaction.followup.send("Invalid embed type!", ephemeral=True)
        return

    await interaction.followup.send("Embed sent!", ephemeral=True)


@bot.tree.command(
    name="request",
    description="Requests a score to upload!",
)
@app_commands.describe(replay_url="Akatsuki replay URL")
async def request(
    interaction: discord.Interaction,
    replay_url: str,
) -> None:
    await interaction.response.defer(ephemeral=True)

    channel = await bot.fetch_channel(settings.ADMIN_SCOREWATCH_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send(
            "Failed to find the scorewatch channel!",
            ephemeral=True,
        )
        return

    assert interaction.guild is not None
    role = interaction.guild.get_role(settings.AKATSUKI_SCOREWATCH_ROLE_ID)
    assert role is not None

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

    score_id_str = parsed_url.path[13:]

    if not score_id_str.isnumeric():
        await interaction.followup.send(
            "This is not a valid Akatsuki replay URL!\n"
            "Valid syntax: `https://akatsuki.gg/web/replays/XXXXXXXX`",
            ephemeral=True,
        )
        return

    score_id = int(score_id_str)

    osu_replay = await osu_replays.get_replay(score_id)
    if not osu_replay:
        await interaction.followup.send(
            "Failed to parse the replay file!",
            ephemeral=True,
        )
        return

    request_data = await sw_requests.fetch_one(score_id)
    if request_data:
        await interaction.followup.send(
            f"This score has been requested on <t:{int(request_data['created_at'].timestamp())}>, "
            f"current status: **{request_data['request_status']}**!",
            ephemeral=True,
        )
        return

    relax = 0
    relax_text = "VN"
    if osu_replay.mods & Mod.Relax:
        relax = 1
        relax_text = "RX"
    elif osu_replay.mods & Mod.Autopilot:
        relax = 2
        relax_text = "AP"

    score_data = await scores.fetch_one(score_id, relax)
    if not score_data:
        await interaction.followup.send(
            "Could not find this score!",
            ephemeral=True,
        )
        return

    thread_starter_message_embed = discord.Embed(
        title="Score Upload Request",
        description=f"{interaction.user.mention} requested a score upload for score ID **[{score_id}](https://akatsuki.gg/web/replays/{score_id})**",
        color=0x3498DB,
    )

    thread_starter_message_embed.add_field(
        name="Basic Details",
        value=textwrap.dedent(
            f"""\
                ▸ Player: [{score_data['user']['username']}](https://akatsuki.gg/u/{score_data['user']['id']})
                ▸ Map: [{score_data['beatmap']['song_name']}](https://akatsuki.gg/b/{score_data['beatmap']['beatmap_id']})
            """,
        ),
        inline=False,
    )
    thread_starter_message_embed.set_footer(
        text="🔽 For specific details see the thread 🔽",
    )

    thread_starter_message = await channel.send(embed=thread_starter_message_embed)
    status = Status.PENDING

    await interaction.followup.send(
        f"Request successfully sent, current status: **{status}**!",
        ephemeral=True,
    )

    thread_name = f"[{relax_text}] {score_data['user']['username']} - {score_data['beatmap']['song_name']}"
    if len(thread_name) > 100:
        thread_name = thread_name[:95] + "..."

    thread_starter_message.guild = interaction.guild
    thread = await thread_starter_message.create_thread(
        name=thread_name,
    )

    users_mentions = set(map(lambda x: x.mention, role.members))
    thread_embed = await thread.send(
        content=textwrap.dedent(
            f"""\
                Hey, <@&{settings.AKATSUKI_SCOREWATCH_ROLE_ID}>! A new upload request has been submitted.

                **Remember you can only vote once!**

                **Vote with the buttons below!**
                **0**/{len(users_mentions)} voted!

                Votes to accept:

                Votes to deny:

                List of people left to vote:
                {', '.join(users_mentions)}
            """,
        ),
        file=discord.File(
            io.BytesIO(osu_replay.raw_replay_data),
            filename=f"{score_id}.osr",
        ),
        view=views.ScorewatchButtonView(score_id, bot),
    )

    request_data = await sw_requests.create(
        interaction.user.id,
        score_id,
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
    name="generate",
    description="Generates score upload metadata!",
)
@app_commands.describe(
    score_id="Score ID",
    username="(Optional) Player username",
    artist="(Optional) Map artist",
    title="(Optional) Map title",
    difficulty_name="(Optional) Map difficulty name",
)
async def generate(
    interaction: discord.Interaction,
    score_id: str,
    username: str = "",
    artist: str = "",
    title: str = "",
    difficulty_name: str = "",
) -> None:
    await interaction.response.defer()

    assert interaction.guild is not None
    role = interaction.guild.get_role(settings.AKATSUKI_SCOREWATCH_ROLE_ID)
    assert role is not None

    assert isinstance(interaction.user, discord.Member)
    if role not in interaction.user.roles and interaction.user.id not in SW_WHITELIST:
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

    relax = scorewatch.get_relax_from_score_id(int(score_id))
    score_data = await scores.fetch_one(int(score_id), relax)
    if not score_data:
        await interaction.followup.send(
            "Could not find this score!",
            ephemeral=True,
        )
        return

    upload_data = await scorewatch.generate_score_upload_resources(
        score_data,
        username,
        artist,
        title,
        difficulty_name,
    )

    if isinstance(upload_data, str):
        await interaction.followup.send(upload_data)
        return

    await interaction.followup.send(
        "\n".join(
            (
                "**Title:**",
                f"```{upload_data['title']}```",
                "",
                "**Description:**",
                f"```{upload_data['description']}```",
                "",
                "**Thumbnail:**",
            ),
        ),
        file=discord.File(
            io.BytesIO(upload_data["image_data"]),
            filename="thumbnail.jpg",
        ),
    )


if __name__ == "__main__":
    logger.configure_logging()
    bot.run(settings.DISCORD_TOKEN)
