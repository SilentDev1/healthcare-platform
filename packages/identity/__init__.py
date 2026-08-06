from packages.identity.matcher import IdentityInput, MatchResult, match_facility
from packages.identity.normalization import (
    address_hash,
    normalize_address,
    normalize_domain,
    normalize_identifier,
    normalize_name,
    normalize_phone,
    normalize_postal_code,
)

__all__ = [
    "IdentityInput",
    "MatchResult",
    "address_hash",
    "match_facility",
    "normalize_address",
    "normalize_domain",
    "normalize_identifier",
    "normalize_name",
    "normalize_phone",
    "normalize_postal_code",
]
