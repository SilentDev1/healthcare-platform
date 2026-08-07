import json
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityPriceSource,
    PriceSourceDiscoveryObservation,
    PriceSourceDiscoveryRun,
)

OFFICIAL_DOMAINS = {
    "ALICE PECK DAY MEMORIAL HOSPITAL": "https://www.alicepeckday.org",
    "ANDROSCOGGIN VALLEY HOSPITAL": "https://www.avhnh.org",
    "CATHOLIC MEDICAL CENTER": "https://www.catholicmedicalcenter.org",
    "CHESHIRE MEDICAL CENTER": "https://www.cheshiremed.org",
    "CONCORD HOSPITAL": "https://www.concordhospital.org",
    "CONCORD HOSPITAL- FRANKLIN": "https://www.concordhospital.org",
    "CONCORD HOSPITAL- LACONIA": "https://www.concordhospital.org",
    "COTTAGE HOSPITAL": "https://www.cottagehospital.org",
    "ELLIOT HOSPITAL": "https://www.elliothospital.org",
    "EXETER HOSPITAL INC": "https://www.exeterhospital.com",
    "FRISBIE MEMORIAL HOSPITAL": "https://frisbiehospital.com",
    "HAMPSTEAD HOSPITAL & RESIDENTIAL TREATMENT FACILIT": "https://www.dhhs.nh.gov",
    "HUGGINS HOSPITAL": "https://www.hugginshospital.org",
    "LITTLETON REGIONAL HEALTHCARE": "https://littletonhealthcare.org",
    "MARY HITCHCOCK MEMORIAL HOSPITAL": "https://www.dartmouth-hitchcock.org",
    "MEMORIAL HOSPITAL, THE": "https://www.mainehealth.org/memorial-hospital",
    "MONADNOCK COMMUNITY HOSPITAL": "https://www.monadnockcommunityhospital.com",
    "NEW HAMPSHIRE HOSPITAL": "https://www.dhhs.nh.gov",
    "NEW LONDON HOSPITAL": "https://www.newlondonhospital.org",
    "PARKLAND MEDICAL CENTER": "https://parklandmedicalcenter.com",
    "PORTSMOUTH REGIONAL HOSPITAL": "https://portsmouthhospital.com",
    "SOUTHERN NH MEDICAL CENTER": "https://www.snhhealth.org",
    "SPEARE MEMORIAL HOSPITAL": "https://spearehospital.com",
    "ST JOSEPH HOSPITAL": "https://stjosephhospital.com",
    "UPPER CONNECTICUT VALLEY HOSPITAL": "https://www.ucvh.org",
    "VALLEY REGIONAL HOSPITAL": "https://vrh.org",
    "WEEKS MEDICAL CENTER": "https://weeksmedical.org",
    "WENTWORTH-DOUGLASS HOSPITAL": "https://www.wdhospital.org",
}


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


@dataclass
class DiscoverySummary:
    facilities_examined: int = 0
    facilities_with_txt: int = 0
    facilities_with_sources: int = 0
    sources_found: int = 0
    sources_updated: int = 0
    facilities_missing: int = 0
    failed: int = 0


def extract_mrf_urls(content: str, base_url: str) -> list[str]:
    urls: list[str] = []
    try:
        payload = json.loads(content)
        stack: list[object] = [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
            elif (
                isinstance(item, str)
                and item.startswith(("http://", "https://"))
                and any(token in item.lower() for token in (".csv", ".json", ".zip", ".gz"))
            ):
                urls.append(item)
    except json.JSONDecodeError:
        for token in content.replace("\r", "\n").split():
            candidate = token.strip("\"',;[]()")
            if candidate.startswith(("http://", "https://")) and any(
                ext in candidate.lower() for ext in (".csv", ".json", ".zip", ".gz")
            ):
                urls.append(candidate)
    return list(dict.fromkeys(urljoin(base_url, url) for url in urls))


def discover_sources(session: Session, client: httpx.Client | None = None) -> DiscoverySummary:
    owned_client = client is None
    http = client or httpx.Client(
        timeout=20,
        follow_redirects=True,
        max_redirects=5,
        headers={"User-Agent": "CareCompare-HPT-Research/1.0"},
    )
    summary = DiscoverySummary()
    run = PriceSourceDiscoveryRun(status="running")
    session.add(run)
    session.flush()
    try:
        for facility in session.scalars(
            select(Facility).where(Facility.active.is_(True)).order_by(Facility.id)
        ):
            summary.facilities_examined += 1
            domain = facility.website_url or OFFICIAL_DOMAINS.get(facility.legal_name)
            if not domain:
                summary.facilities_missing += 1
                continue
            if not facility.website_url:
                facility.website_url = domain
            parsed = urlparse(domain)
            root = f"{parsed.scheme}://{parsed.netloc}"
            txt_url = f"{root}/cms-hpt.txt"
            urls: list[str] = []
            method = "cms_hpt_txt"
            try:
                response = http.get(txt_url)
                content_type = response.headers.get("content-type")
                if response.status_code == 200 and len(response.content) <= 2_000_000:
                    urls = extract_mrf_urls(response.text, txt_url)
                    if urls:
                        summary.facilities_with_txt += 1
                session.add(
                    PriceSourceDiscoveryObservation(
                        run_id=run.id,
                        facility_id=facility.id,
                        candidate_url=txt_url,
                        source_page_url=domain,
                        discovery_method=method,
                        content_type=content_type,
                        http_status=response.status_code,
                        confidence_score=1 if urls else 0,
                        status="source_found" if urls else "not_found",
                        reason="Parsed root cms-hpt.txt"
                        if urls
                        else "No valid MRF URL in cms-hpt.txt",
                        metadata_json={
                            "final_url": str(response.url),
                            "redirect_count": len(response.history),
                        },
                        observed_at=datetime.now(UTC),
                    )
                )
                if not urls:
                    method = "deterministic_html_discovery"
                    page = http.get(domain)
                    if page.status_code == 200 and len(page.content) <= 5_000_000:
                        parser = _LinkParser()
                        parser.feed(page.text)
                        for href in parser.links:
                            candidate = urljoin(str(page.url), href)
                            host = urlparse(candidate).hostname or ""
                            relevant = any(
                                token in candidate.lower()
                                for token in ("price", "chargemaster", "standard-charge")
                            )
                            downloadable = any(
                                ext in candidate.lower() for ext in (".csv", ".json", ".zip", ".gz")
                            )
                            if (
                                (host == parsed.hostname or host.endswith(f".{parsed.hostname}"))
                                and relevant
                                and downloadable
                            ):
                                urls.append(candidate)
            except httpx.HTTPError as exc:
                summary.failed += 1
                session.add(
                    PriceSourceDiscoveryObservation(
                        run_id=run.id,
                        facility_id=facility.id,
                        candidate_url=txt_url,
                        source_page_url=domain,
                        discovery_method=method,
                        status="failed",
                        reason=f"{type(exc).__name__}: {exc}"[:1000],
                        metadata_json={},
                        observed_at=datetime.now(UTC),
                    )
                )
            urls = list(dict.fromkeys(urls))
            if urls:
                summary.facilities_with_sources += 1
            else:
                summary.facilities_missing += 1
            for url in urls:
                existing = session.scalar(
                    select(FacilityPriceSource).where(
                        FacilityPriceSource.facility_id == facility.id,
                        FacilityPriceSource.machine_readable_file_url == url,
                    )
                )
                if existing:
                    existing.last_seen_at = datetime.now(UTC)
                    summary.sources_updated += 1
                else:
                    session.add(
                        FacilityPriceSource(
                            facility_id=facility.id,
                            source_type="hospital_mrf",
                            source_page_url=domain,
                            machine_readable_file_url=url,
                            cms_hpt_txt_url=txt_url if method == "cms_hpt_txt" else None,
                            active=True,
                            discovery_method=method,
                            first_seen_at=datetime.now(UTC),
                            last_seen_at=datetime.now(UTC),
                        )
                    )
                    summary.sources_found += 1
        run.status = "completed"
    except Exception as exc:
        run.status = "failed"
        run.error_summary = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        if owned_client:
            http.close()
        run.finished_at = datetime.now(UTC)
        run.facilities_examined = summary.facilities_examined
        run.sources_found = summary.sources_found
        run.sources_updated = summary.sources_updated
        run.sources_missing = summary.facilities_missing
        run.sources_failed = summary.failed
        session.commit()
    return summary
