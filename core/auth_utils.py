import os
import re
import hashlib
from typing import Tuple


NAME_CLAIM_RE = re.compile(r"\b(?:i[' ]?m|i am|my name is)\s+(.{2,80})$", re.IGNORECASE)


def normalize_name(name: str) -> str:
    name = " ".join((name or "").strip().split())
    return name.upper()


def extract_claimed_name(text: str) -> str | None:
    m = NAME_CLAIM_RE.search((text or "").strip())
    if not m:
        return None
    return normalize_name(m.group(1))


SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_LEN = 32


def hash_passphrase(passphrase: str, salt: bytes | None = None) -> Tuple[str, str]:
    salt = salt or os.urandom(16)
    h = hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_LEN)
    return salt.hex(), h.hex()


def verify_passphrase(stored_salt_hex: str, stored_hash_hex: str, attempt: str) -> bool:
    try:
        salt = bytes.fromhex(stored_salt_hex)
        expected = bytes.fromhex(stored_hash_hex)
        calc = hashlib.scrypt(attempt.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_LEN)
        # constant-time compare
        return hashlib.compare_digest(calc, expected)
    except Exception:
        return False

