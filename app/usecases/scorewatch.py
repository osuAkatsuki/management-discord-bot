import datetime
import os
import typing

import aiosu
import discord
from aiosu.models.mods import Mod
from discord.ext import commands
from slider import Beatmap

from app import osu
from app import state
from app.common import settings
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


async def generate_normal_metadata(
    score_data: Score,
    username: str | None = None,
    artist: str | None = None,
    title: str | None = None,
    difficulty_name: str | None = None,
    detail_text: str | None = None,
    detail_colour: str | None = None,
) -> dict[str, str] | str:
    replay_path = os.path.join(settings.DATA_DIR, "replay", f"{score_data['id']}.osr")
    if not os.path.exists(replay_path):
        await state.http_client.download_file(
            f"https://akatsuki.gg/web/replays/{score_data['id']}",
            replay_path,
            is_replay=True,
        )

    if not os.path.exists(replay_path):
        return "This replay does not exist!"

    replay_file = aiosu.utils.replay.parse_path(replay_path)

    relax = 0
    relax_text = "Vanilla"
    if replay_file.mods & Mod.Relax:
        relax = 1
        relax_text = "Relax"
    elif replay_file.mods & Mod.Autopilot:
        relax = 2
        relax_text = "Autopilot"

    mode_icon = osu.int_to_osu_name(replay_file.mode.value)
    title_colour = get_title_colour(relax)

    osu_file_path = await osu.download_osu_file(score_data["beatmap"]["beatmap_id"])
    if not osu_file_path:
        return "Couldn't find this beatmap!"

    osz_file_path = await osu.download_osz_file(score_data["beatmap"]["beatmapset_id"])
    if not osz_file_path:
        return "Couldn't find this beatmapset!"

    # TODO: Temponary use this parser until me and aesth write one for aiosu.
    beatmap = Beatmap.from_path(osu_file_path)

    if not os.path.exists(
        os.path.join(
            settings.DATA_DIR,
            "finals",
            "backgrounds",
            f"{score_data['beatmap']['beatmap_id']}_normal.png",
        ),
    ):
        background_image = osu.find_beatmap_background(
            score_data["beatmap"]["beatmap_id"],
            score_data["beatmap"]["beatmapset_id"],
        )
        if not background_image:
            return "Couldn't find background of this map!"

        postprocessed_img = postprocessing.apply_effects_normal_template(
            background_image,
        )
        postprocessed_img.save(
            os.path.join(
                settings.DATA_DIR,
                "finals",
                "backgrounds",
                f"{score_data['beatmap']['beatmap_id']}_normal.png",
            ),
        )

    map_full_combo = typing.cast(int, beatmap.max_combo)
    if not detail_text and not detail_colour:
        detail_text, detail_colour = calculate_detail_text_and_colour(score_data)

    if not artist:
        artist = beatmap.artist

    if not title:
        title = beatmap.title

    if not difficulty_name:
        difficulty_name = beatmap.version

    if not username:
        username = score_data["user"]["username"]

    with open(os.path.join("templates", "scorewatch_normal.html")) as f:
        tempalate = f.read()

    tempalate = tempalate.replace(
        r"<% bg-image %>",
        (
            "/bot-data"  # mounted in docker; DON'T TOUCH
            + "/"
            + "finals"
            + "/"
            + "backgrounds"
            + "/"
            + f"{score_data['beatmap']['beatmap_id']}_normal.png"
        ),
    )
    tempalate = tempalate.replace(r"<% misc-colour %>", detail_colour)  # type: ignore
    tempalate = tempalate.replace(r"<% title-colour %>", title_colour)
    tempalate = tempalate.replace(r"<% username %>", username)
    tempalate = tempalate.replace(r"<% mode %>", mode_icon)
    tempalate = tempalate.replace(r"<% country %>", score_data["user"]["country"])
    tempalate = tempalate.replace(r"<% userid %>", str(score_data["user"]["id"]))
    tempalate = tempalate.replace(r"<% artist %>", artist)  # type: ignore
    tempalate = tempalate.replace(r"<% title %>", title)  # type: ignore
    tempalate = tempalate.replace(r"<% map-diff %>", difficulty_name)  # type: ignore
    tempalate = tempalate.replace(r"<% mods %>", f"+{replay_file.mods}")
    tempalate = tempalate.replace(r"<% combo %>", str(replay_file.max_combo))
    tempalate = tempalate.replace(r"<% max-combo %>", str(map_full_combo))
    tempalate = tempalate.replace(r"<% pp-val %>", str(int(score_data["pp"])))
    tempalate = tempalate.replace(r"<% acc %>", f"{score_data['accuracy']:.2f}")
    tempalate = tempalate.replace(r"<% misc-text %>", detail_text)  # type: ignore

    with open(
        os.path.join(
            settings.DATA_DIR,
            "finals",
            "html",
            f"{score_data['beatmap']['beatmap_id']}_{score_data['user']['id']}_score.html",
        ),
        "w",
    ) as f:
        f.write(tempalate)

    url = os.path.join(
        "/bot-data",  # mounted in docker; DON'T TOUCH
        "finals",
        "html",
        f"{score_data['beatmap']['beatmap_id']}_{score_data['user']['id']}_score.html",
    )

    state.webdriver.capture_web_canvas(
        "file://" + url,
        os.path.join(
            settings.DATA_DIR,
            "finals",
            "thumbnails",
            f"{score_data['beatmap']['beatmap_id']}_{score_data['user']['id']}_score.png",
        ),
    )

    # convert to jpg because of youtube limit.
    img = postprocessing.convert_to_jpg(
        os.path.join(
            settings.DATA_DIR,
            "finals",
            "thumbnails",
            f"{score_data['beatmap']['beatmap_id']}_{score_data['user']['id']}_score.png",
        ),
    )
    img.save(
        os.path.join(
            settings.DATA_DIR,
            "finals",
            "thumbnails",
            f"{score_data['beatmap']['beatmap_id']}_{score_data['user']['id']}_score.jpg",
        ),
        format="JPEG",
        subsampling=0,
        quality=100,
    )

    performance_data = await performance.fetch_one(
        score_data["beatmap"]["beatmap_id"],
        replay_file.mode.id,
        int(replay_file.mods),
        replay_file.max_combo,
        score_data["accuracy"],
        replay_file.statistics.count_miss,
    )

    if not performance_data:
        return "Couldn't find performance data for this score!"

    song_name = f"{artist} - {title} [{difficulty_name}]"
    title = (
        f"[{performance_data['stars']:.2f} ⭐] {relax_text} | {username} | "
        f"{song_name} +{replay_file.mods} {score_data['accuracy']:.2f}% {int(performance_data['pp'])}pp {detail_text}"
    )

    description = "\n".join(
        (
            f"Player: https://akatsuki.gg/u/{score_data['user']['id']}",
            "Server: https://akatsuki.gg",
            f"Map: https://akatsuki.gg/b/{score_data['beatmap']['beatmap_id']}",
            "",
            "Recorded by <recorder nick>",
            # "Thumbnail by <nick of who generated thumbnail>",
            "Uploaded by <uploader nick>",
            "------------------",
            "Akatsuki is an osu! private server, featuring a normal and relax server with many active users! Join our discord here! https://akatsuki.gg/discord",
        ),
    )

    return {
        "title": title,
        "description": description,
        "file": os.path.join(
            settings.DATA_DIR,
            "finals",
            "thumbnails",
            f"{score_data['beatmap']['beatmap_id']}_{score_data['user']['id']}_score.jpg",
        ),
    }
