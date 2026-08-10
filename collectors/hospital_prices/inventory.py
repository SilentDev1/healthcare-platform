"""NH hospital inventory loader and validator.

Loads the canonical hospital inventory from fixtures and provides
lookup functions used by discovery, health_systems, and classification modules.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HospitalEntry:
    legal_name: str
    cms_ccn: str
    npi: str
    health_system: str | None
    health_system_domain: str | None
    official_website: str
    transparency_page_candidates: list[str]
    cms_hpt_txt_url: str | None
    known_aliases: list[str]
    parent_org: str | None
    facility_type: str
    latitude: float
    longitude: float
    status: str
    exclusion_reason: str | None


@dataclass(frozen=True)
class HealthSystemEntry:
    name: str
    domain: str
    members: list[str]


@dataclass
class HospitalInventory:
    hospitals: list[HospitalEntry]
    health_systems: dict[str, HealthSystemEntry]
    _by_name: dict[str, HospitalEntry]
    _by_ccn: dict[str, HospitalEntry]

    @property
    def active_hospitals(self) -> list[HospitalEntry]:
        return [h for h in self.hospitals if h.status == "active"]

    @property
    def excluded_hospitals(self) -> list[HospitalEntry]:
        return [h for h in self.hospitals if h.status != "active"]

    def get_by_name(self, legal_name: str) -> HospitalEntry | None:
        return self._by_name.get(legal_name.upper().strip())

    def get_by_ccn(self, ccn: str) -> HospitalEntry | None:
        return self._by_ccn.get(ccn.strip())

    def get_domain(self, legal_name: str) -> str | None:
        entry = self.get_by_name(legal_name)
        return entry.official_website if entry else None

    def get_system_members(self, system_name: str) -> list[HospitalEntry]:
        system = self.health_systems.get(system_name)
        if not system:
            return []
        return [h for h in self.hospitals if h.health_system == system_name]

    def get_system_for_hospital(self, legal_name: str) -> HealthSystemEntry | None:
        entry = self.get_by_name(legal_name)
        if entry and entry.health_system:
            return self.health_systems.get(entry.health_system)
        return None


_DEFAULT_FIXTURE = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "fixtures"
    / "nh_hospital_inventory.json"
)

_cached_inventory: HospitalInventory | None = None


def load_inventory(path: Path | None = None) -> HospitalInventory:
    """Load hospital inventory from JSON fixture. Cached after first load."""
    global _cached_inventory
    if _cached_inventory is not None and path is None:
        return _cached_inventory

    fixture_path = path or _DEFAULT_FIXTURE
    with fixture_path.open() as f:
        data = json.load(f)

    hospitals = [_parse_hospital(h) for h in data["hospitals"]]
    systems: dict[str, HealthSystemEntry] = {}
    for name, info in data.get("health_systems", {}).items():
        systems[name] = HealthSystemEntry(name=name, domain=info["domain"], members=info["members"])

    by_name = {h.legal_name.upper(): h for h in hospitals}
    by_ccn = {h.cms_ccn: h for h in hospitals}

    inventory = HospitalInventory(
        hospitals=hospitals, health_systems=systems, _by_name=by_name, _by_ccn=by_ccn
    )

    if path is None:
        _cached_inventory = inventory
    return inventory


def validate_inventory(inventory: HospitalInventory) -> list[str]:
    """Validate inventory integrity. Returns list of error messages."""
    errors: list[str] = []
    ccns: set[str] = set()
    for h in inventory.hospitals:
        if not h.legal_name:
            errors.append("Hospital missing legal_name")
        if not h.cms_ccn:
            errors.append(f"{h.legal_name}: missing cms_ccn")
        elif h.cms_ccn in ccns:
            errors.append(f"{h.legal_name}: duplicate cms_ccn {h.cms_ccn}")
        ccns.add(h.cms_ccn)
        if not h.official_website:
            errors.append(f"{h.legal_name}: missing official_website")
        if h.status not in ("active", "excluded_psychiatric"):
            errors.append(f"{h.legal_name}: invalid status {h.status}")
        if h.health_system and h.health_system not in inventory.health_systems:
            errors.append(f"{h.legal_name}: unknown health_system {h.health_system}")
    for name, system in inventory.health_systems.items():
        for member in system.members:
            if member.upper() not in inventory._by_name:
                errors.append(f"Health system {name}: unknown member {member}")
    return errors


def get_official_domains(inventory: HospitalInventory | None = None) -> dict[str, str]:
    """Return {legal_name: official_website} dict, replacing OFFICIAL_DOMAINS in discovery.py."""
    inv = inventory or load_inventory()
    return {h.legal_name: h.official_website for h in inv.hospitals if h.status == "active"}


def _parse_hospital(data: dict[str, Any]) -> HospitalEntry:
    return HospitalEntry(
        legal_name=data["legal_name"],
        cms_ccn=data["cms_ccn"],
        npi=data["npi"],
        health_system=data.get("health_system"),
        health_system_domain=data.get("health_system_domain"),
        official_website=data["official_website"],
        transparency_page_candidates=data.get("transparency_page_candidates", []),
        cms_hpt_txt_url=data.get("cms_hpt_txt_url"),
        known_aliases=data.get("known_aliases", []),
        parent_org=data.get("parent_org"),
        facility_type=data["facility_type"],
        latitude=data.get("latitude", 0.0),
        longitude=data.get("longitude", 0.0),
        status=data.get("status", "active"),
        exclusion_reason=data.get("exclusion_reason"),
    )
