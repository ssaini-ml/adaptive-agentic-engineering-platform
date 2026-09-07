from package.base import BaseRepository
from package.models import User


class UserRepository(BaseRepository):
    def get(self, item_id: int) -> User | None:
        return User(item_id, "Lin") if item_id == 1 else None

