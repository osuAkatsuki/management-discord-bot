from enum import Enum


class VoteType(Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


class Status(Enum):
    UNKNOWN = "unknown"
    PENDING = "pending"
    ACCEPTED = "accepted"
    DENIED = "denied"
    TIED = "tied"
    UPLOADED = "uploaded"

    def __str__(self) -> str:
        return self.value

    @staticmethod
    def resolved_statuses() -> list[str]:
        return [
            Status.ACCEPTED.value,
            Status.DENIED.value,
            Status.UPLOADED.value,
        ]

    @property
    def embed_colour(self) -> int:
        return {
            Status.ACCEPTED: 10352512,
            Status.DENIED: 16220288,
            Status.TIED: 15565824,
        }.get(self, 16246912)
