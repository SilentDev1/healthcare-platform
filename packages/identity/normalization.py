import hashlib
import re
import unicodedata
from urllib.parse import urlparse

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SUFFIXES = {"inc", "incorporated", "llc", "corp", "corporation", "co", "company"}


def _ascii(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()


def normalize_name(value: str) -> str:
    words = [word for word in _NON_ALNUM.sub(" ", _ascii(value)).split() if word not in _SUFFIXES]
    return " ".join(words)


def normalize_address(value: str) -> str:
    replacements = {
        "street": "st",
        "road": "rd",
        "avenue": "ave",
        "boulevard": "blvd",
        "suite": "ste",
    }
    words = _NON_ALNUM.sub(" ", _ascii(value)).split()
    return " ".join(replacements.get(word, word) for word in words)


def normalize_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_postal_code(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())[:5]


def normalize_domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").lower().removeprefix("www.")


def normalize_identifier(identifier_type: str, value: str) -> str:
    if identifier_type == "PHONE":
        return normalize_phone(value)
    if identifier_type == "DOMAIN":
        return normalize_domain(value)
    return _NON_ALNUM.sub("", _ascii(value))


def address_hash(address: str, city: str, state: str, postal_code: str) -> str:
    normalized = "|".join(
        (
            normalize_address(address),
            normalize_name(city),
            state.upper(),
            normalize_postal_code(postal_code),
        )
    )
    return hashlib.sha256(normalized.encode()).hexdigest()
