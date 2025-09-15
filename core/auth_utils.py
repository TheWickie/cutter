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


def _normalize_passphrase(p: str) -> str:
    # Trim, collapse spaces, and normalise common curly quotes to ASCII
    s = (p or "").strip()
    s = s.replace("\u2018", "'").replace("\u2019", "'")  # left/right single quote
    s = s.replace("\u201C", '"').replace("\u201D", '"')  # left/right double quote
    s = " ".join(s.split())
    return s


def hash_passphrase(passphrase: str, salt: bytes | None = None) -> Tuple[str, str]:
    salt = salt or os.urandom(16)
    norm = _normalize_passphrase(passphrase)
    h = hashlib.scrypt(norm.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_LEN)
    return salt.hex(), h.hex()


def verify_passphrase(stored_salt_hex: str, stored_hash_hex: str, attempt: str) -> bool:
    try:
        salt = bytes.fromhex(stored_salt_hex)
        expected = bytes.fromhex(stored_hash_hex)
        norm = _normalize_passphrase(attempt)
        calc = hashlib.scrypt(norm.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_LEN)
        # constant-time compare
        return hashlib.compare_digest(calc, expected)
    except Exception:
        return False
