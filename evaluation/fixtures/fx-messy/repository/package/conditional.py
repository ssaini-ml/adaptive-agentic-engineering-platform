from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from package.repository import UserRepository


def accepts_repository(repository: "UserRepository") -> object:
    return repository

