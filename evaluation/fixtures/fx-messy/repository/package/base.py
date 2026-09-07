from typing import Protocol


class BaseRepository(Protocol):
    def get(self, item_id: int) -> object | None:
        ...

