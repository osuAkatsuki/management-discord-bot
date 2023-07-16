from __future__ import annotations

import glob

import os
import shutil
import zipfile

from app import settings
from app import state


def safe_name(s: str) -> str:
    return s.lower().strip().replace(" ", "_")


async def download_osu_file(beatmap_id: int) -> str:
    path = os.path.join(settings.DATA_DIR, "beatmap", f"{beatmap_id}.osu")

    if os.path.exists(path):
        return path

    url = f"https://osu.ppy.sh/osu/{beatmap_id}"

    await state.http_client.download_file(url, path)
    return path


async def download_osz_file(beatmapset_id: int) -> str:
    path = os.path.join(settings.DATA_DIR, "beatmap", str(beatmapset_id))

    if os.path.exists(path):
        return path

    url = f"https://osu.direct/api/d/{beatmapset_id}"

    await state.http_client.download_file(url, path + ".zip")

    with zipfile.ZipFile(path + ".zip", "r") as zip_ref:
        zip_ref.extractall(path)

    os.remove(path + ".zip")

    # make sure all files are case sensitive to safe name
    for item in glob.glob(path + "/**/*", recursive=True):
        path_name = item.split("/")[-1]
        safe_path_name = safe_name(path_name)

        try:
            shutil.move(item, os.path.join(path, safe_path_name))
        except Exception:
            rest_path = item.split("/" + path_name)[0]
            safe_rest_path = safe_name(rest_path)
            shutil.move(  # if not, cry.
                os.path.join(safe_rest_path, path_name),
                os.path.join(safe_rest_path, safe_path_name),
            )

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
