from __future__ import annotations

import os

from app import state
from app.common import settings


def safe_name(s: str) -> str:
    return s.lower().strip().replace(" ", "_")


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
