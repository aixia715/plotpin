import secrets
import string

_ALPHABET = string.ascii_letters + string.digits


def new_id(length: int = 10) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
