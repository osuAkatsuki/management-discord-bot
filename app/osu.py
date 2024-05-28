from __future__ import annotations

import glob
import os
import shutil
import zipfile
from typing import Optional

from app import state
from app.common import settings


def safe_name(s: str) -> str:
    return s.lower().strip().replace(" ", "_")


async def download_osu_file(beatmap_id: int) -> str:
    path = os.path.join(settings.DATA_DIR, "beatmap", f"{beatmap_id}.osu")

    if os.path.exists(path):
        return path

    url = f"https://osu.ppy.sh/osu/{beatmap_id}"

    await state.http_client.download_file(url, path)
    return path


def parse_beatmap_metadata_from_file_data(file_data: bytes) -> dict[str, str]:
    lines = file_data.decode().splitlines()
    beatmap = {}
    for line in lines[1:]:
        if line.startswith("Artist:"):
            beatmap["artist"] = line.split(":")[1].strip()
        elif line.startswith("Title:"):
            beatmap["title"] = line.split(":")[1].strip()
        elif line.startswith("Creator:"):
            beatmap["creator"] = line.split(":")[1].strip()
        elif line.startswith("Version:"):
            beatmap["version"] = line.split(":")[1].strip()

    return beatmap


async def try_download_osz_file(beatmap_id: int, path: str) -> bool:
    mirrors = [
        "https://chimu.moe/d/",
        "https://api.osu.direct/d/",
        "https://catboy.best/d/",
    ]

    for mirror in mirrors:
        try:
            await state.http_client.download_file(
                mirror + str(beatmap_id),
                path + ".zip",
            )
        except Exception as e:
            continue

        if not os.path.exists(path + ".zip"):
            continue

        if os.path.getsize(path + ".zip") < 100:  # safe number
            os.remove(path + ".zip")
            continue

    if not os.path.exists(path + ".zip"):
        return False

    return True


def find_beatmap_background_filename(beatmap_id: int, beatmapset_id: int) -> str:
    background_path = ""
    osu_file_path = os.path.join(settings.DATA_DIR, "beatmap", f"{beatmap_id}.osu")

    if not os.path.exists(osu_file_path):
        return background_path

    with open(osu_file_path, encoding="utf-8-sig") as f:
        lines = f.readlines()

    for line in lines:
        if line.startswith("0,0,"):
            background_path = line.split(",")[2].strip().strip('"')
            break

    return safe_name(background_path)


def to_osu_mode_readable(mode: int) -> str:
    return {
        0: "osu!std",
        1: "osu!taiko",
        2: "osu!ctb",
        3: "osu!mania",
    }[mode]


def int_to_osu_name(mode: int) -> str:
    return {
        0: "osu",
        1: "taiko",
        2: "fruits",
        3: "mania",
    }[mode]
