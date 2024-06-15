import datetime
from io import BytesIO
import os
import typing
import base64

import aiosu
import discord
from app import state
from discord.ext import commands

from app import osu
from app import osu_beatmaps
from app.adapters import aws_s3
from app.constants import DetailTextColour
from app.constants import Status
from app.repositories import performance
from app.repositories.scores import Score
from app.repositories.sw_requests import ScorewatchRequest
from app.usecases import postprocessing


def get_title_colour(relax: int) -> str:
    return {  # from old psd template.
        0: "#cde7ff",
        1: "#fcff96",
        2: "#c5ff96",
    }[relax]


RELAX_OFFSET = 500000000
AP_OFFSET = 6148914691236517204


def get_relax_from_score_id(score_id: int) -> int:
    if score_id < RELAX_OFFSET:
        return 1
    elif score_id >= AP_OFFSET:
        return 2

    return 0


def calculate_detail_text_and_colour(score_data: Score) -> tuple[str, str]:
    detail_text = "FC"
    detail_colour = DetailTextColour.FC
    if (
        score_data["count_miss"] == 0
        and score_data["max_combo"] <= score_data["beatmap"]["max_combo"] * 0.9
    ):
        detail_text = "SB"
        detail_colour = DetailTextColour.SB
    elif score_data["count_miss"] != 0:
        detail_text = f"{score_data['count_miss']}xMiss"
        detail_colour = DetailTextColour.MISS

    return detail_text, detail_colour.value


async def format_request_embed(
    bot: commands.Bot,
    score_data: Score,
    request_data: ScorewatchRequest,
    status: Status | None = None,
) -> discord.Embed:
    detail_text, _ = calculate_detail_text_and_colour(score_data)

    mods = aiosu.models.mods.Mods(score_data["mods"])
    mode_name = osu.int_to_osu_name(score_data["play_mode"])

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
            ▸ Mode: {osu.to_osu_mode_readable(score_data['play_mode'])}
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


class ScoreUploadResources(typing.TypedDict):
    title: str
    description: str
    image_data: bytes


async def generate_score_upload_resources(
    score_data: Score,
    username: str | None = None,
    artist: str | None = None,
    title: str | None = None,
    difficulty_name: str | None = None,
    detail_text: str | None = None,
    detail_colour: str | None = None,
) -> ScoreUploadResources | str:
    relax = get_relax_from_score_id(int(score_data["id"]))
    relax_text = "Vanilla"
    if relax == 1:
        relax_text = "Relax"
    elif relax == 2:
        relax_text = "Autopilot"

    mods = aiosu.models.mods.Mods(score_data["mods"])
    mode_icon = osu.int_to_osu_name(score_data["play_mode"])
    title_colour = get_title_colour(relax)

    user_id = score_data["user"]["id"]

    beatmap_id = score_data["beatmap"]["beatmap_id"]
    beatmapset_id = score_data["beatmap"]["beatmapset_id"]

    beatmap_bytes = await osu_beatmaps.get_beatmap(beatmap_id)

    if not beatmap_bytes:
        return "Couldn't find this beatmap!"

    beatmap = osu_beatmaps.parse_beatmap_metadata(beatmap_bytes)
    beatmap_background_image = await osu_beatmaps.get_beatmap_background_image(
        beatmap_id, beatmapset_id
    )

    if not beatmap_background_image:
        return "Couldn't find this beatmap!"

    beatmap_background_image = postprocessing.apply_effects_normal_template(
        beatmap_background_image,
    )

    if not detail_text and not detail_colour:
        detail_text, detail_colour = calculate_detail_text_and_colour(score_data)

    if not artist:
        artist = beatmap["artist"]

    if not title:
        title = beatmap["title"]

    if not difficulty_name:
        difficulty_name = beatmap["version"]

    if not username:
        username = score_data["user"]["username"]

    with open(os.path.join("templates", "scorewatch_normal.html")) as f:
        template = f.read()

    with BytesIO() as background_buffer:
        beatmap_background_image.save(background_buffer, format="PNG")
        template = template.replace(
            r"<% bg-image %>",
            base64.b64encode(background_buffer.getvalue()).decode("utf-8"),
        )

    template = template.replace(r"<% misc-colour %>", detail_colour)  # type: ignore
    template = template.replace(r"<% title-colour %>", title_colour)
    template = template.replace(r"<% username %>", username)
    template = template.replace(r"<% mode %>", mode_icon)
    template = template.replace(r"<% country %>", score_data["user"]["country"])
    template = template.replace(r"<% userid %>", str(score_data["user"]["id"]))
    template = template.replace(r"<% artist %>", artist)  # type: ignore
    template = template.replace(r"<% title %>", title)  # type: ignore
    template = template.replace(r"<% map-diff %>", difficulty_name)  # type: ignore
    template = template.replace(r"<% mods %>", f"+{mods}")

    if beatmap["max_combo"] > 0:
        template = template.replace(
            r"<% combo %>",
            f"{score_data['max_combo']}x/{beatmap['max_combo']}x",
        )
    else:
        template = template.replace(
            r"<% combo %>",
            f"{score_data['score']:,} ({score_data['max_combo']}x)",
        )

    template = template.replace(r"<% pp-val %>", str(int(score_data["pp"])))
    template = template.replace(r"<% acc %>", f"{score_data['accuracy']:.2f}")
    template = template.replace(r"<% misc-text %>", detail_text)  # type: ignore

    thumbnail_image_data = state.webdriver.capture_html_as_jpeg_image(template)

    # await aws_s3.save_object_data(
    #     f"/scorewatch/thumbnails/{beatmap_id}_{user_id}_score.jpg",
    #     thumbnail_image_data,
    # )

    performance_data = await performance.fetch_one(
        score_data["beatmap"]["beatmap_md5"],
        score_data["beatmap"]["beatmap_id"],
        score_data["play_mode"],
        score_data["mods"],
        score_data["max_combo"],
        score_data["accuracy"],
        score_data["count_miss"],
    )

    if not performance_data:
        return "Couldn't find performance data for this score!"

    song_name = f"{artist} - {title} [{difficulty_name}]"
    title_detail_text = detail_text.replace("xMiss", "❌")  # type: ignore

    title = (
        f"[{performance_data['stars']:.2f} ⭐] {relax_text} | {username} | "
        f"{song_name} +{mods} {score_data['accuracy']:.2f}% {int(performance_data['pp'])}pp {title_detail_text}"
    )

    description = "\n".join(
        (
            f"Player: https://akatsuki.gg/u/{score_data['user']['id']}",
            "Server: https://akatsuki.gg",
            f"Map: https://akatsuki.gg/b/{score_data['beatmap']['beatmap_id']}",
            "",
            "Recorded by <>",
            # "Thumbnail by <>",
            "Uploaded by <>",
            "------------------",
            "Akatsuki is an osu! private server, featuring a normal and relax server with many active users! Join our discord here! https://akatsuki.gg/discord",
        ),
    )

    return {
        "title": title,
        "description": description,
        "image_data": thumbnail_image_data,
    }
