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


def parse_osu_file_manually(path: str) -> dict[str, str]:
    with open(path, encoding="utf-8-sig") as f:
        lines = f.readlines()

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

        if os.path.getsize(path + ".zip") > 0:
            return True

        os.remove(path + ".zip")

    return False


async def download_osz_file(beatmapset_id: int) -> Optional[str]:
    path = os.path.join(settings.DATA_DIR, "beatmap", str(beatmapset_id))

    if os.path.exists(path):
        return path

    success = await try_download_osz_file(beatmapset_id, path)
    if not success:
        return None

    with zipfile.ZipFile(path + ".zip", "r") as zip_ref:
        zip_ref.extractall(path)

    os.remove(path + ".zip")

    # make sure all folders are lowercase
    for item in glob.glob(path + "/**/", recursive=True):
        path_name = item.split("/")[-1]  # /sb/(f)
        safe_path_name = safe_name(path_name)

        if path_name == safe_path_name:
            continue

        shutil.move(item, os.path.join(path, safe_path_name))

    # make sure all files are lowercase
    for item in glob.glob(path + "/**/*.*", recursive=True):
        path_name = item.split("/")[-1]  # /sb/f/(file.png)
        safe_path_name = safe_name(path_name)

        if path_name == safe_path_name:
            continue

        shutil.move(item, os.path.join(path, safe_path_name))

    return path


def find_beatmap_background(beatmap_id: int, beatmapset_id: int) -> str:
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

    return os.path.join(
        settings.DATA_DIR,
        "beatmap",
        str(beatmapset_id),
        safe_name(background_path),
    )


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
