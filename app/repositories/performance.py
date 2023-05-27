from app import state

from typing import TypedDict
from typing import cast


class Performance(TypedDict):
    pp: float
    stars: float


async def fetch_one(
    beatmap_id: int,
    mode: int,
    mods: int,
    max_combo: int,
    accuracy: float,
    miss_count: int,
) -> Performance | None:
    res = await state.http_client.post(
        "https://performance.akatsuki.gg/api/v1/calculate",
        json=[
            {
                "beatmap_id": beatmap_id,
                "mode": mode,
                "mods": mods,
                "max_combo": max_combo,
                "accuracy": accuracy,
                "miss_count": miss_count,
            },
        ],
    )
    resp = res.json()

    if not resp:
        return None

    rec = {
        "pp": resp[0]["pp"],
        "stars": resp[0]["stars"],
    }

    return cast(Performance, rec)