"""Encryption helpers for sensitive columns.

OAuth tokens are encrypted at rest with Fernet (symmetric AES-128-CBC +
HMAC). The key comes from the TOKEN_ENCRYPTION_KEY environment variable —
generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os

from cryptography.fernet import Fernet
from sqlalchemy.types import Text, TypeDecorator

_PREFIX = 'enc::'


def _fernet() -> Fernet:
    key = os.environ.get('TOKEN_ENCRYPTION_KEY')
    if not key:
        raise RuntimeError(
            'TOKEN_ENCRYPTION_KEY is not set — required to read/write encrypted '
            'OAuth tokens. See src/utils/crypto.py for how to generate one.'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedString(TypeDecorator):
    """Column type that transparently encrypts values at rest.

    Stored values are prefixed with 'enc::' so plaintext legacy rows (there
    should be none post-purge) are still readable and get re-encrypted on
    the next write.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _PREFIX + _fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.startswith(_PREFIX):
            return _fernet().decrypt(value[len(_PREFIX):].encode()).decode()
        return value
