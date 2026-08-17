"""Strict location-identity verification for provider-neutral image enrichment."""

from __future__ import annotations

from collectors.facility_media.pipeline import MediaCandidate
from scripts.enrich_location_media import verify_identity


def _cand(title: str, attribution: str | None = None) -> MediaCandidate:
    return MediaCandidate(
        title=title, image_url="u", description_url="d", license_type="CC BY-SA 4.0",
        license_url="l", attribution_text=attribution, copyright_owner=None,
        width=1200, height=800, mime_type="image/jpeg", is_free=True,
    )


def test_accepts_when_name_token_and_city_both_present() -> None:
    ok, reason = verify_identity(
        _cand("File:Elliot Hospital, Manchester, New Hampshire.jpg"),
        facility_name="ELLIOT HOSPITAL", org_name="Elliot Health System", city="Manchester",
    )
    assert ok and "matched_city" in reason


def test_rejects_when_city_missing_even_if_name_matches() -> None:
    # Same org, WRONG city (another branch / HQ) -> must reject.
    ok, reason = verify_identity(
        _cand("File:Quest Diagnostics building, Secaucus, New Jersey.jpg"),
        facility_name="Quest Diagnostics — Nashua", org_name="Quest Diagnostics", city="Nashua",
    )
    assert not ok and reason == "city_not_in_candidate"


def test_rejects_when_no_distinctive_name_token() -> None:
    # City present but nothing tying the photo to THIS provider -> reject (stock/other building).
    ok, reason = verify_identity(
        _cand("File:Downtown Nashua New Hampshire skyline.jpg"),
        facility_name="Apple Therapy Services — Nashua", org_name="Apple Therapy Services",
        city="Nashua",
    )
    assert not ok and reason == "no_distinctive_name_token"


def test_generic_words_alone_do_not_verify() -> None:
    # "Hospital"/"Medical"/"Center" are stopwords; a generic hospital photo must not verify.
    ok, _ = verify_identity(
        _cand("File:Generic hospital building, Nashua.jpg"),
        facility_name="Southern NH Medical Center", org_name=None, city="Nashua",
    )
    assert not ok


def test_uses_attribution_text_too() -> None:
    ok, _ = verify_identity(
        _cand("File:IMG_1234.jpg", attribution="Derry Imaging center in Derry, NH / CC BY-SA"),
        facility_name="Derry Imaging — Derry", org_name="Derry Imaging", city="Derry",
    )
    assert ok
