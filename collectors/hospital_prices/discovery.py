"""Multi-strategy hospital MRF discovery engine.

Strategies (ordered by confidence):
1. cms-hpt.txt at root + /.well-known/ (confidence 1.0)
2. Candidate path probing (0.95)
3. robots.txt / sitemap.xml parsing (0.9)
4. Depth-limited link crawl (0.85)
5. Health system directory lookup (delegated to health_systems module)
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.inventory import get_official_domains, load_inventory
from packages.database import (
    Facility,
    FacilityPriceSource,
    PriceSourceDiscoveryObservation,
    PriceSourceDiscoveryRun,
)

# MRF-relevant file extensions
MRF_EXTENSIONS = (".csv", ".json", ".zip", ".gz", ".gzip", ".xml")

# URL path keywords indicating price transparency content
MRF_KEYWORDS = (
    "price",
    "pricing",
    "transparency",
    "chargemaster",
    "charge-master",
    "standard-charge",
    "standardcharge",
    "standard_charge",
    "machine-readable",
    "machine_readable",
    "mrf",
    "shoppable",
)

# Candidate paths to probe directly
CANDIDATE_PATHS = (
    "/price-transparency",
    "/pricing",
    "/standardcharges",
    "/standard-charges",
    "/transparency",
    "/patient-resources/billing",
    "/patients-visitors/billing",
    "/patients/billing",
    "/financial-information",
    "/chargemaster",
    "/billing-financial",
    "/billing",
    "/patient-financial-services",
    "/patients-and-visitors/billing-and-insurance",
)

# Maximum pages to crawl per facility for link-based discovery
MAX_PAGES_PER_FACILITY = 20
MAX_CRAWL_DEPTH = 2
CRAWL_TIMEOUT_SECONDS = 30
RESPONSE_SIZE_CAP = 5_000_000  # 5MB


class _LinkParser(HTMLParser):
    """Extracts href and downloadable links from HTML."""

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
    strategies_used: dict[str, int] = field(default_factory=dict)


def extract_mrf_urls(content: str, base_url: str) -> list[str]:
    """Extract MRF-like URLs from JSON or text content."""
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
                and any(token in item.lower() for token in MRF_EXTENSIONS)
            ):
                urls.append(item)
    except json.JSONDecodeError:
        for token in content.replace("\r", "\n").split():
            candidate = token.strip("\"',;[]()")
            if candidate.startswith(("http://", "https://")) and any(
                ext in candidate.lower() for ext in MRF_EXTENSIONS
            ):
                urls.append(candidate)
    return list(dict.fromkeys(urljoin(base_url, url) for url in urls))


def _check_cms_hpt_txt(
    http: httpx.Client, root: str, run_id: object, facility_id: object, session: Session
) -> tuple[list[str], str | None]:
    """Strategy 1: Check cms-hpt.txt at root and /.well-known/."""
    urls: list[str] = []
    txt_url_found: str | None = None
    for path in ("/cms-hpt.txt", "/.well-known/cms-hpt.txt"):
        txt_url = f"{root}{path}"
        try:
            response = http.get(txt_url)
            content_type = response.headers.get("content-type")
            found: list[str] = []
            if response.status_code == 200 and len(response.content) <= 2_000_000:
                found = extract_mrf_urls(response.text, txt_url)
                if found:
                    urls.extend(found)
                    txt_url_found = txt_url
            session.add(
                PriceSourceDiscoveryObservation(
                    run_id=run_id,
                    facility_id=facility_id,
                    candidate_url=txt_url,
                    source_page_url=root,
                    discovery_method="cms_hpt_txt",
                    content_type=content_type,
                    http_status=response.status_code,
                    confidence_score=1.0 if found else 0.0,
                    status="source_found" if found else "not_found",
                    reason="Parsed cms-hpt.txt" if found else "No valid MRF URL",
                    metadata_json={
                        "final_url": str(response.url),
                        "redirect_count": len(response.history),
                    },
                    observed_at=datetime.now(UTC),
                )
            )
        except httpx.HTTPError:
            pass
    return list(dict.fromkeys(urls)), txt_url_found


def _check_candidate_paths(
    http: httpx.Client,
    root: str,
    hostname: str,
    run_id: object,
    facility_id: object,
    session: Session,
) -> list[str]:
    """Strategy 2: Probe well-known transparency paths for downloadable links."""
    urls: list[str] = []
    for path in CANDIDATE_PATHS:
        page_url = f"{root}{path}"
        try:
            response = http.get(page_url)
            if response.status_code != 200 or len(response.content) > RESPONSE_SIZE_CAP:
                continue
            content_type = (response.headers.get("content-type") or "").lower()
            if "html" in content_type:
                found = _extract_downloadable_urls(response.text, str(response.url), hostname)
                urls.extend(found)
                if found:
                    session.add(
                        PriceSourceDiscoveryObservation(
                            run_id=run_id,
                            facility_id=facility_id,
                            candidate_url=page_url,
                            source_page_url=root,
                            discovery_method="candidate_path_probe",
                            content_type=content_type,
                            http_status=response.status_code,
                            confidence_score=0.95,
                            status="source_found",
                            reason=f"Found {len(found)} MRF links at {path}",
                            metadata_json={"path": path},
                            observed_at=datetime.now(UTC),
                        )
                    )
        except httpx.HTTPError:
            continue
    return list(dict.fromkeys(urls))


def _parse_robots_txt(
    http: httpx.Client,
    root: str,
    hostname: str,
    run_id: object,
    facility_id: object,
    session: Session,
) -> tuple[list[str], list[str]]:
    """Strategy 3a: Parse robots.txt for Sitemap directives and MRF-keyword paths."""
    sitemap_urls: list[str] = []
    mrf_urls: list[str] = []
    try:
        response = http.get(f"{root}/robots.txt")
        if response.status_code == 200 and len(response.content) <= 500_000:
            for line in response.text.splitlines():
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    if sitemap_url.startswith(("http://", "https://")):
                        sitemap_urls.append(sitemap_url)
                # Look for Allow/Disallow paths with MRF keywords
                if any(kw in line.lower() for kw in MRF_KEYWORDS):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        path = parts[1].strip()
                        if path.startswith("/"):
                            candidate = f"{root}{path}"
                            if any(ext in candidate.lower() for ext in MRF_EXTENSIONS):
                                mrf_urls.append(candidate)
    except httpx.HTTPError:
        pass
    return sitemap_urls, mrf_urls


def _parse_sitemap(
    http: httpx.Client,
    sitemap_url: str,
    hostname: str,
    max_depth: int = 2,
) -> list[str]:
    """Strategy 3b: Recursively parse sitemaps for MRF-keyword URLs."""
    urls: list[str] = []
    if max_depth <= 0:
        return urls
    try:
        response = http.get(sitemap_url)
        if response.status_code != 200 or len(response.content) > RESPONSE_SIZE_CAP:
            return urls
        content = response.text
        # Check for sitemap index
        try:
            tree = ElementTree.fromstring(content)  # noqa: S314
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            # Sitemap index → recurse
            for sitemap_loc in tree.findall(".//sm:sitemap/sm:loc", ns):
                if sitemap_loc.text:
                    urls.extend(_parse_sitemap(http, sitemap_loc.text, hostname, max_depth - 1))
            # URL entries
            for url_loc in tree.findall(".//sm:url/sm:loc", ns):
                if url_loc.text:
                    loc = url_loc.text.strip()
                    loc_lower = loc.lower()
                    if any(kw in loc_lower for kw in MRF_KEYWORDS) or any(
                        ext in loc_lower for ext in MRF_EXTENSIONS
                    ):
                        host = urlparse(loc).hostname or ""
                        if host == hostname or host.endswith(f".{hostname}"):
                            urls.append(loc)
        except ElementTree.ParseError:
            pass
    except httpx.HTTPError:
        pass
    return list(dict.fromkeys(urls))


def _crawl_page_links(
    http: httpx.Client,
    start_url: str,
    hostname: str,
    run_id: object,
    facility_id: object,
    session: Session,
) -> list[str]:
    """Strategy 4: Depth-limited link crawl for MRF URLs."""
    urls: list[str] = []
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(start_url, 0)]
    crawl_start = time.monotonic()
    pages_crawled = 0

    while queue and pages_crawled < MAX_PAGES_PER_FACILITY:
        if time.monotonic() - crawl_start > CRAWL_TIMEOUT_SECONDS:
            break
        current_url, depth = queue.pop(0)
        if current_url in visited or depth > MAX_CRAWL_DEPTH:
            continue
        visited.add(current_url)
        try:
            response = http.get(current_url)
            pages_crawled += 1
            if response.status_code != 200 or len(response.content) > RESPONSE_SIZE_CAP:
                continue
            content_type = (response.headers.get("content-type") or "").lower()
            if "html" not in content_type:
                continue
            found = _extract_downloadable_urls(response.text, str(response.url), hostname)
            urls.extend(found)
            if depth < MAX_CRAWL_DEPTH:
                parser = _LinkParser()
                parser.feed(response.text)
                for href in parser.links:
                    abs_url = urljoin(str(response.url), href)
                    link_host = urlparse(abs_url).hostname or ""
                    if (
                        link_host == hostname or link_host.endswith(f".{hostname}")
                    ) and abs_url not in visited:
                        link_lower = abs_url.lower()
                        if any(kw in link_lower for kw in MRF_KEYWORDS):
                            queue.append((abs_url, depth + 1))
        except httpx.HTTPError:
            continue
    if urls:
        session.add(
            PriceSourceDiscoveryObservation(
                run_id=run_id,
                facility_id=facility_id,
                candidate_url=start_url,
                source_page_url=start_url,
                discovery_method="depth_limited_crawl",
                http_status=200,
                confidence_score=0.85,
                status="source_found",
                reason=(
                    f"Crawl found {len(urls)} MRF links "
                    f"({pages_crawled} pages, depth {MAX_CRAWL_DEPTH})"
                ),
                metadata_json={"pages_crawled": pages_crawled},
                observed_at=datetime.now(UTC),
            )
        )
    return list(dict.fromkeys(urls))


def _extract_downloadable_urls(html: str, page_url: str, hostname: str) -> list[str]:
    """Extract MRF-relevant downloadable URLs from HTML content."""
    urls: list[str] = []
    parser = _LinkParser()
    parser.feed(html)
    for href in parser.links:
        candidate = urljoin(page_url, href)
        host = urlparse(candidate).hostname or ""
        candidate_lower = candidate.lower()
        # Must be same domain (or subdomain)
        if not (host == hostname or host.endswith(f".{hostname}")) and not any(
            vendor in host
            for vendor in ("turquoise", "cleverley", "medicopy", "amazonaws.com", "blob.core")
        ):
            continue
        relevant = any(token in candidate_lower for token in MRF_KEYWORDS)
        downloadable = any(ext in candidate_lower for ext in MRF_EXTENSIONS)
        if relevant and downloadable or downloadable and _looks_like_mrf_url(candidate_lower):
            urls.append(candidate)
    return urls


def _looks_like_mrf_url(url_lower: str) -> bool:
    """Heuristic: does this URL look like it might be a hospital MRF?"""
    return bool(
        re.search(r"(standard.?charge|machine.?read|mrf|chargemaster|price.?transp)", url_lower)
    )


def discover_sources(session: Session, client: httpx.Client | None = None) -> DiscoverySummary:
    """Run multi-strategy discovery across all active NH facilities."""
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

    # Load inventory-based domain mapping
    inventory = load_inventory()
    official_domains = get_official_domains(inventory)

    try:
        for facility in session.scalars(
            select(Facility).where(Facility.active.is_(True)).order_by(Facility.id)
        ):
            summary.facilities_examined += 1
            domain = facility.website_url or official_domains.get(facility.legal_name)
            if not domain:
                summary.facilities_missing += 1
                continue
            if not facility.website_url:
                facility.website_url = domain
            parsed = urlparse(domain)
            hostname = parsed.hostname or ""
            root = f"{parsed.scheme}://{parsed.netloc}"
            urls: list[str] = []
            method = "cms_hpt_txt"

            try:
                # Strategy 1: cms-hpt.txt
                txt_urls, txt_url = _check_cms_hpt_txt(http, root, run.id, facility.id, session)
                if txt_urls:
                    urls.extend(txt_urls)
                    summary.facilities_with_txt += 1
                    method = "cms_hpt_txt"
                    summary.strategies_used["cms_hpt_txt"] = (
                        summary.strategies_used.get("cms_hpt_txt", 0) + 1
                    )

                # Strategy 2: Candidate path probing
                if not urls:
                    path_urls = _check_candidate_paths(
                        http, root, hostname, run.id, facility.id, session
                    )
                    if path_urls:
                        urls.extend(path_urls)
                        method = "candidate_path_probe"
                        summary.strategies_used["candidate_path_probe"] = (
                            summary.strategies_used.get("candidate_path_probe", 0) + 1
                        )

                # Strategy 3: robots.txt + sitemap
                if not urls:
                    sitemap_urls, robots_mrf_urls = _parse_robots_txt(
                        http, root, hostname, run.id, facility.id, session
                    )
                    urls.extend(robots_mrf_urls)
                    # Also try default sitemap if not found in robots.txt
                    if not sitemap_urls:
                        sitemap_urls = [f"{root}/sitemap.xml"]
                    for sitemap_url in sitemap_urls[:3]:  # Cap at 3 sitemaps
                        sitemap_found = _parse_sitemap(http, sitemap_url, hostname)
                        urls.extend(sitemap_found)
                    if urls:
                        method = "sitemap_crawl"
                        summary.strategies_used["sitemap_crawl"] = (
                            summary.strategies_used.get("sitemap_crawl", 0) + 1
                        )

                # Strategy 4: Depth-limited link crawl
                if not urls:
                    # Also try transparency page candidates from inventory
                    entry = inventory.get_by_name(facility.legal_name)
                    crawl_seeds = [domain]
                    if entry:
                        crawl_seeds.extend(entry.transparency_page_candidates)
                    for seed in crawl_seeds[:5]:
                        crawl_urls = _crawl_page_links(
                            http, seed, hostname, run.id, facility.id, session
                        )
                        urls.extend(crawl_urls)
                        if urls:
                            method = "depth_limited_crawl"
                            summary.strategies_used["depth_limited_crawl"] = (
                                summary.strategies_used.get("depth_limited_crawl", 0) + 1
                            )
                            break

                # Strategy 4b: Direct probe of transparency_page_candidates
                if not urls and entry and entry.transparency_page_candidates:
                    for candidate_url in entry.transparency_page_candidates[:5]:
                        try:
                            resp = http.get(candidate_url)
                            if resp.status_code == 200 and len(resp.content) <= RESPONSE_SIZE_CAP:
                                ct = (resp.headers.get("content-type") or "").lower()
                                if "html" in ct:
                                    found = _extract_downloadable_urls(
                                        resp.text, str(resp.url), hostname
                                    )
                                    if found:
                                        urls.extend(found)
                                        method = "transparency_candidate_probe"
                                        summary.strategies_used[
                                            "transparency_candidate_probe"
                                        ] = (
                                            summary.strategies_used.get(
                                                "transparency_candidate_probe", 0
                                            )
                                            + 1
                                        )
                                        session.add(
                                            PriceSourceDiscoveryObservation(
                                                run_id=run.id,
                                                facility_id=facility.id,
                                                candidate_url=candidate_url,
                                                source_page_url=domain,
                                                discovery_method="transparency_candidate_probe",
                                                content_type=ct,
                                                http_status=resp.status_code,
                                                confidence_score=0.9,
                                                status="source_found",
                                                reason=f"Found {len(found)} MRF links",
                                                metadata_json={
                                                    "candidate": candidate_url,
                                                },
                                                observed_at=datetime.now(UTC),
                                            )
                                        )
                                        break
                        except httpx.HTTPError:
                            continue

                # Strategy 4c: Try domain variants (with/without www)
                if not urls:
                    alt_roots = []
                    if hostname.startswith("www."):
                        alt_roots.append(f"https://{hostname[4:]}")
                    else:
                        alt_roots.append(f"https://www.{hostname}")
                    for alt_root in alt_roots:
                        alt_host = urlparse(alt_root).hostname or ""
                        alt_txt, _ = _check_cms_hpt_txt(
                            http, alt_root, run.id, facility.id, session
                        )
                        if alt_txt:
                            urls.extend(alt_txt)
                            method = "domain_variant_txt"
                            summary.strategies_used["domain_variant_txt"] = (
                                summary.strategies_used.get("domain_variant_txt", 0) + 1
                            )
                            break
                        alt_paths = _check_candidate_paths(
                            http, alt_root, alt_host, run.id, facility.id, session
                        )
                        if alt_paths:
                            urls.extend(alt_paths)
                            method = "domain_variant_path"
                            summary.strategies_used["domain_variant_path"] = (
                                summary.strategies_used.get("domain_variant_path", 0) + 1
                            )
                            break

                # Strategy 5: Check health system domain
                if not urls and entry and entry.health_system_domain:
                    sys_root = f"https://www.{entry.health_system_domain}"
                    sys_hostname = entry.health_system_domain
                    sys_txt_urls, _ = _check_cms_hpt_txt(
                        http, sys_root, run.id, facility.id, session
                    )
                    if sys_txt_urls:
                        urls.extend(sys_txt_urls)
                        method = "health_system_txt"
                        summary.strategies_used["health_system_txt"] = (
                            summary.strategies_used.get("health_system_txt", 0) + 1
                        )
                    if not urls:
                        sys_path_urls = _check_candidate_paths(
                            http, sys_root, sys_hostname, run.id, facility.id, session
                        )
                        if sys_path_urls:
                            urls.extend(sys_path_urls)
                            method = "health_system_path"
                            summary.strategies_used["health_system_path"] = (
                                summary.strategies_used.get("health_system_path", 0) + 1
                            )

            except httpx.HTTPError as exc:
                summary.failed += 1
                session.add(
                    PriceSourceDiscoveryObservation(
                        run_id=run.id,
                        facility_id=facility.id,
                        candidate_url=root,
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
