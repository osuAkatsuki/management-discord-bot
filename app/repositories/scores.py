from typing import cast
from typing import TypedDict

from app import state


class User(TypedDict):
    id: int
    username: str
    country: str


class Beatmap(TypedDict):
    beatmap_md5: str
    beatmap_id: int
    beatmapset_id: int
    song_name: str
    ar: float
    od: float
    max_combo: int


class Score(TypedDict):
    user: User
    beatmap: Beatmap
    id: str
    score: int
    max_combo: int
    full_combo: bool
    mods: int
    count_300: int
    count_100: int
    count_50: int
    count_miss: int
    count_katu: int
    count_geki: int
    play_mode: int
    accuracy: float
    pp: float
    rank: str


async def fetch_one(score_id: int, relax: int) -> Score | None:
    res = await state.http_client.get(
        f"https://akatsuki.gg/api/v1/score?id={score_id}&rx={relax}",
    )
    resp = res.json()

    if not resp or resp["code"] != 200:
        return None

    rec = {
        "user": {
            "id": resp["score"]["user"]["id"],
            "username": resp["score"]["user"]["username"],
            "country": resp["score"]["user"]["country"],
        },
        "beatmap": {
            "beatmap_md5": resp["beatmap"]["beatmap_md5"],
            "beatmap_id": resp["beatmap"]["beatmap_id"],
            "beatmapset_id": resp["beatmap"]["beatmapset_id"],
            "song_name": resp["beatmap"]["song_name"],
            "ar": resp["beatmap"]["ar"],
            "od": resp["beatmap"]["od"],
            "max_combo": resp["beatmap"]["max_combo"],
        },
        "id": resp["score"]["id"],
        "score": resp["score"]["score"],
        "max_combo": resp["score"]["max_combo"],
        "full_combo": resp["score"]["full_combo"],
        "mods": resp["score"]["mods"],
        "count_300": resp["score"]["count_300"],
        "count_100": resp["score"]["count_100"],
        "count_50": resp["score"]["count_50"],
        "count_miss": resp["score"]["count_miss"],
        "count_katu": resp["score"]["count_katu"],
        "count_geki": resp["score"]["count_geki"],
        "play_mode": resp["score"]["play_mode"],
        "accuracy": resp["score"]["accuracy"],
        "pp": resp["score"]["pp"],
        "rank": resp["score"]["rank"],
    }

    return cast(Score, rec)
