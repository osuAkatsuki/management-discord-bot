from typing import cast
from typing import TypedDict

from app import state


class User(TypedDict):
    id: int
    username: str


async def fetch_one(_type: str, user_id: int | str) -> User | None:
    res = await state.http_client.get(
        f"https://akatsuki.gg/api/v1/users/full?{_type}={user_id}",
    )
    resp = res.json()

    if not resp or resp["code"] != 200:
        return None

    rec = {
        "id": resp["id"],
        "username": resp["username"],
    }

    return cast(User, rec)
