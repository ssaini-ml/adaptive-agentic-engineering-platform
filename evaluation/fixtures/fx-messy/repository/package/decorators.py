from collections.abc import Callable
from functools import wraps


def traced(function: Callable):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return function(*args, **kwargs)

    return wrapper

