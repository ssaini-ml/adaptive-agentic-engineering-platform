from package.repository import UserRepository as Repository

from package.decorators import traced


@traced
def find_user(user_id: int):
    return Repository().get(user_id)

