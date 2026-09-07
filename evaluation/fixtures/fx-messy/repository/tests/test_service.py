from package.service import find_user


def test_find_user() -> None:
    assert find_user(1).name == "Lin"

