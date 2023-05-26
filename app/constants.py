from enum import Enum


class VoteType(Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


class TemplateMiscTextColour(Enum):
    FC = "#f0cb58"
    SB = "#63943b"
    MISS = "#e95e69"


class Status(Enum):
    UNKNOWN = "unknown"
    PENDING = "pending"
    ACCEPTED = "accepted"
    DENIED = "denied"
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
        }.get(self, 16246912)
