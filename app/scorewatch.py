import datetime
import discord
import aiosu

from discord.ext import commands

from app.repositories import scores
from app.repositories import sw_requests

from app.repositories.sw_requests import ScorewatchRequest

from app.constants import Status
from app import osu_format


def title_colour(relax: int) -> str:
    return {  # from old psd template.
        0: "#cde7ff",
        1: "#fcff96",
        2: "#c5ff96",
    }[relax]


async def generate_scorewatch_embed(
    bot: commands.Bot,
    request_data: ScorewatchRequest,
    status: Status | None = None,
) -> discord.Embed | str:  # embed or error.
    score_data = await scores.fetch_one(
        request_data["score_id"], request_data["score_relax"]
    )
    if not score_data:
        return "Couldn't find this play!"

    detail_text = "FC"
    if (
        score_data["count_miss"] == 0
        and score_data["max_combo"] <= score_data["beatmap"]["max_combo"] * 0.9
    ):
        detail_text = "SB?"
    elif score_data["count_miss"] != 0:
        detail_text = f"{score_data['count_miss']}xMiss"

    return await format_request_embed(
        bot, score_data, request_data, detail_text, status
    )


async def format_request_embed(
    bot: commands.Bot,
    score_data: scores.Score,
    request_data: ScorewatchRequest,
    detail_text: str,
    status: Status | None = None,
) -> discord.Embed:
    mods = aiosu.models.mods.Mods(score_data["mods"])
    mode_name = osu_format.int_to_osu_name(score_data["play_mode"])

    if not status:
        status = Status(request_data["request_status"])

    requested_by = await bot.fetch_user(request_data["requested_by"])

    embed = discord.Embed(
        title=f"Upload Request: {status.value.title()}",
        description=f"""\
            Player: [{score_data['user']['username']}](https://akatsuki.gg/u/{score_data['user']['id']})
            Leaderboard: [Click here!](https://akatsuki.gg/b/{score_data['beatmap']['beatmap_id']})
            Replay: [Click here!](https://akatsuki.gg/web/replays/{score_data['id']})
        """,
        color=status.embed_colour,
        timestamp=datetime.datetime.utcnow(),
    )
    embed.add_field(
        name="Score Information:",
        value=f"""\
            ▸ Mode: {osu_format.to_osu_mode_readable(score_data['play_mode'])}
            ▸ Map: [{score_data['beatmap']['song_name']}](https://osu.ppy.sh/beatmapsets/{score_data['beatmap']['beatmapset_id']}#{mode_name}/{score_data['beatmap']['beatmap_id']})
            ▸ Score: +{mods} {detail_text} {score_data['accuracy']:.2f}% {score_data['pp']:.0f}pp
            ▸ Combo: {score_data['max_combo']}x/{score_data['beatmap']['max_combo']}x
        """,
    )
    embed.set_footer(text=f"Requested by {requested_by.name} ({requested_by.id})")
    embed.set_image(
        url=f"https://assets.ppy.sh/beatmaps/{score_data['beatmap']['beatmapset_id']}/covers/card.jpg",
    )

    return embed
