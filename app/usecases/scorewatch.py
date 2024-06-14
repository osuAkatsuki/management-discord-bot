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

    # if not os.path.exists(replay_path):
    #    return "This replay does not exist!"

    relax = get_relax_from_score_id(int(score_data["id"]))
    relax_text = "Vanilla"
    if relax == 1:
        relax_text = "Relax"
    elif relax == 2:
        relax_text = "Autopilot"

    mods = aiosu.models.mods.Mods(score_data["mods"])

    osu_file_path = await osu.download_osu_file(score_data["beatmap"]["beatmap_id"])
    if not osu_file_path:
        return "Couldn't find this beatmap!"

    osz_file_path = await osu.download_osz_file(score_data["beatmap"]["beatmapset_id"])
    if not osz_file_path:
        return "Couldn't find this beatmapset!"

    # TODO: Temponary use this parser until me and aesth write one for aiosu.
    try:
        beatmap = Beatmap.from_path(osu_file_path)
        beatmap_artist = beatmap.artist
        beatmap_title = beatmap.title
        beatmap_difficulty_name = beatmap.version
    except Exception:  # When this happens, it's probably a mania map.
        beatmap = osu.parse_osu_file_manually(osu_file_path)
        beatmap_artist = beatmap["artist"]
        beatmap_title = beatmap["title"]
        beatmap_difficulty_name = beatmap["version"]

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

    if not detail_text and not detail_colour:
        detail_text, detail_colour = calculate_detail_text_and_colour(score_data)

    if not artist:
        artist = beatmap_artist

    if not title:
        title = beatmap_title

    if not difficulty_name:
        difficulty_name = beatmap_difficulty_name

    if not username:
        username = score_data["user"]["username"]

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

    with open(os.path.join("templates", "scorewatch_normal.html")) as f:
        template = f.read()

    template = template.replace(
        r"<% beatmap.background_url %>",
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
    template = template.replace(r"<% user.id %>", str(score_data["user"]["id"]))
    template = template.replace(
        r"<% score.grade %>", score_data["rank"].lower().replace("h", "")
    )
    template = template.replace(
        r"<% score.rank_golden_html %>",
        "rank-golden" if "H" in score_data["rank"] else "",
    )
    template = template.replace(
        r"<% score.is_fc_html %>", "is-fc" if score_data["full_combo"] else ""
    )
    template = template.replace(r"<% user.username %>", username)
    template = template.replace(
        r"<% user.country_code %>", score_data["user"]["country"].lower()
    )
    template = template.replace(r"<% score.pp %>", str(int(score_data["pp"])))
    template = template.replace(
        r"<% score.accuracy %>", f"{score_data['accuracy']:.2f}"
    )

    mods_html = []
    modifiers = [relax_text]
    for mod in mods:

        if Mod.Nightcore in mods and mod is Mod.DoubleTime:
            continue
        if Mod.Perfect in mods and mod is Mod.SuddenDeath:
            continue

        if mod == Mod.TouchDevice:
            modifiers.append("Touchscreen")
            continue

        mods_html.append(f'<div class="mod hard">{mod.short_name}</div>')

    for modifier in modifiers:
        mods_html.append(f'<div class="mod modifier">{modifier}</div>')

    template = template.replace(
        r"<% score.mods_html %>", "\n          ".join(mods_html)
    )

    template = template.replace(
        r"<% score.grade_upper %>", score_data["rank"].replace("H", "")
    )
    template = template.replace(r"<% beatmap.name %>", title)
    template = template.replace(r"<% beatmap.artist %>", artist)
    template = template.replace(r"<% beatmap.version %>", difficulty_name)
    template = template.replace(
        r"<% beatmap.difficulty %>", f"{performance_data['stars']:.2f}"
    )

    with open(
        os.path.join(
            settings.DATA_DIR,
            "finals",
            "html",
            f"{score_data['beatmap']['beatmap_id']}_{score_data['user']['id']}_score.html",
        ),
        "w",
    ) as f:
        f.write(template)

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
        "file": os.path.join(
            settings.DATA_DIR,
            "finals",
            "thumbnails",
            f"{score_data['beatmap']['beatmap_id']}_{score_data['user']['id']}_score.jpg",
        ),
    }
