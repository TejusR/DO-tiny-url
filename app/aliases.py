import secrets
import string

ALIAS_LENGTH = 10
ALIAS_ALPHABET = string.ascii_lowercase + string.digits


def generate_alias() -> str:
    """Generate a cryptographically random automatic alias."""
    return "".join(secrets.choice(ALIAS_ALPHABET) for _ in range(ALIAS_LENGTH))
