"""Build data/ny_hospitals_seed.json — the authoritative NY operating hospital denominator.

Deterministic builder (no network). Reconciles the CMS Hospital General Information snapshot
(data/ny_cms_hospital_snapshot.json) with sourced NYSDOH/health-system research to produce the
consumer denominator:

  operating seed = (CMS consumer-type: Acute + CAH + REH)
                   - dispositions (closed / merged / superseded / specialty / rehab_ltac)
                   + additions (operating general-acute hospitals with valid CCNs that CMS Care
                     Compare omits — confirmed operating in NYSDOH Health Facility General
                     Information, dataset vn5v-hh5r).

Region for every hospital is derived from its county via data/ny_region_taxonomy.json (NYC
counties -> boroughs). Federal (VA/DoD), Psychiatric, and Childrens CMS rows are excluded by type
(never part of the consumer denominator). Run: python -m scripts.build_ny_seed
"""

from __future__ import annotations

# ruff: noqa: E501
import json
from pathlib import Path

from scripts.verify_ny_foundation import resolve_region

DATA = Path(__file__).resolve().parent.parent / "data"
CMS = json.loads((DATA / "ny_cms_hospital_snapshot.json").read_text())
TAX = json.loads((DATA / "ny_region_taxonomy.json").read_text())
CMS_BY = {h["facility_id"]: h for h in CMS["hospitals"]}
CONSUMER = ("Acute Care Hospitals", "Critical Access Hospitals", "Rural Emergency Hospital")

# --- Dispositions: CMS consumer-type CCNs removed from the operating denominator -------------
DISPO_CLOSED = [
    {"ccn": "330169", "name": "Mount Sinai Beth Israel", "note": "closed 2025-04-09 after NYSDOH-approved closure plan + litigation; CMS acute tag lags; absent from NYSDOH operating"},
]
DISPO_MERGED = [
    {"ccn": "330246", "name": "St Charles Hospital", "into": "330286", "note": "merged into Good Samaritan University Hospital (2026-07-01) as its St. Charles Campus; shares NYS license/TIN/CCN 330286; do not price separately"},
]
DISPO_SUPERSEDED = [
    {"ccn": "330166", "name": "Westfield Memorial Hospital (acute)", "by": "330801", "note": "converted to a Rural Emergency Hospital; live CCN is REH 330801 (same hospital, Westfield); acute CCN 330166 lags in CMS"},
]
DISPO_SPECIALTY = [
    {"ccn": "330100", "name": "NY Eye and Ear Infirmary of Mount Sinai", "note": "ophthalmology/ENT specialty acute hospital; bucket separately (candidate for later consumer visibility)"},
    {"ccn": "330270", "name": "Hospital for Special Surgery", "note": "orthopedic specialty acute hospital; bucket separately (high-value for hip/knee — candidate for later consumer visibility)"},
]
DISPO_REHAB_LTAC = [
    {"ccn": "330405", "name": "Helen Hayes Hospital", "note": "physical rehabilitation specialty hospital (state-run); not general acute"},
    {"ccn": "330406", "name": "Sunnyview Hospital and Rehabilitation Center", "note": "rehabilitation specialty hospital; not general acute"},
    {"ccn": "330411", "name": "Unity Specialty Hospital", "note": "long-term acute care (LTAC) / specialty unit of Unity; not general acute"},
]
DISPOSED = {d["ccn"] for grp in (DISPO_CLOSED, DISPO_MERGED, DISPO_SUPERSEDED, DISPO_SPECIALTY, DISPO_REHAB_LTAC) for d in grp}

# --- Additions: operating general-acute hospitals CMS Care Compare omits (NYSDOH-confirmed) ---
# CCN, name, city, zip, county, type, system. Region derived from county.
ADDITIONS = [
    {"ccn": "330061", "name": "NewYork-Presbyterian Westchester", "address": "55 Palmer Avenue", "city": "Bronxville", "zip": "10708", "county": "WESTCHESTER", "type": "Acute Care Hospitals", "system": "NewYork-Presbyterian", "ccn_confidence": "moderate (330060/330061 legacy Lawrence ambiguity — verify at MRF time)"},
    {"ccn": "330064", "name": "NewYork-Presbyterian Lower Manhattan Hospital", "address": "170 William Street", "city": "New York", "zip": "10038", "county": "NEW YORK", "type": "Acute Care Hospitals", "system": "NewYork-Presbyterian", "ccn_confidence": "moderate — verify at MRF time"},
    {"ccn": "330072", "name": "Montefiore Wakefield Campus", "address": "600 East 233rd Street", "city": "Bronx", "zip": "10466", "county": "BRONX", "type": "Acute Care Hospitals", "system": "Montefiore"},
    {"ccn": "330088", "name": "Stony Brook Eastern Long Island Hospital", "address": "201 Manor Place", "city": "Greenport", "zip": "11944", "county": "SUFFOLK", "type": "Acute Care Hospitals", "system": "Stony Brook Medicine"},
    {"ccn": "330108", "name": "St Joseph's Hospital (Elmira)", "address": "555 St. Joseph's Boulevard", "city": "Elmira", "zip": "14901", "county": "CHEMUNG", "type": "Acute Care Hospitals", "system": "Arnot Health"},
    {"ccn": "330167", "name": "NYU Langone Hospital - Long Island", "address": "259 First Street", "city": "Mineola", "zip": "11501", "county": "NASSAU", "type": "Acute Care Hospitals", "system": "NYU Langone Health"},
    {"ccn": "330236", "name": "NewYork-Presbyterian Brooklyn Methodist Hospital", "address": "506 Sixth Street", "city": "Brooklyn", "zip": "11215", "county": "KINGS", "type": "Acute Care Hospitals", "system": "NewYork-Presbyterian"},
    {"ccn": "330306", "name": "NYU Langone Hospital - Brooklyn", "address": "150 55th Street", "city": "Brooklyn", "zip": "11220", "county": "KINGS", "type": "Acute Care Hospitals", "system": "NYU Langone Health"},
    {"ccn": "330340", "name": "Stony Brook Southampton Hospital", "address": "240 Meeting House Lane", "city": "Southampton", "zip": "11968", "county": "SUFFOLK", "type": "Acute Care Hospitals", "system": "Stony Brook Medicine"},
    {"ccn": "330353", "name": "Long Island Jewish Forest Hills", "address": "102-01 66th Road", "city": "Forest Hills", "zip": "11375", "county": "QUEENS", "type": "Acute Care Hospitals", "system": "Northwell Health"},
    {"ccn": "330372", "name": "Long Island Jewish Valley Stream", "address": "900 Franklin Avenue", "city": "Valley Stream", "zip": "11580", "county": "NASSAU", "type": "Acute Care Hospitals", "system": "Northwell Health"},
    {"ccn": "330397", "name": "Interfaith Medical Center", "address": "1545 Atlantic Avenue", "city": "Brooklyn", "zip": "11213", "county": "KINGS", "type": "Acute Care Hospitals", "system": "One Brooklyn Health"},
    {"ccn": "330398", "name": "Syosset Hospital", "address": "221 Jericho Turnpike", "city": "Syosset", "zip": "11791", "county": "NASSAU", "type": "Acute Care Hospitals", "system": "Northwell Health"},
]

# --- System map for CMS-sourced hospitals (CCN -> system); "" = independent/unassigned ---------
SYSTEM_MAP = {
    # Northwell
    "330106": "Northwell Health", "330195": "Northwell Health", "330119": "Northwell Health", "330181": "Northwell Health",
    "330045": "Northwell Health", "330331": "Northwell Health", "330185": "Northwell Health", "330107": "Northwell Health",
    "330043": "Northwell Health", "330160": "Northwell Health", "330162": "Northwell Health", "330261": "Northwell Health",
    "330023": "Northwell Health", "330049": "Northwell Health", "330273": "Northwell Health",
    # NYU Langone
    "330214": "NYU Langone Health", "330141": "NYU Langone Health",
    # NYP
    "330101": "NewYork-Presbyterian", "330055": "NewYork-Presbyterian", "330267": "NewYork-Presbyterian",
    # Mount Sinai
    "330024": "Mount Sinai Health System", "330046": "Mount Sinai Health System", "330198": "Mount Sinai Health System",
    # Montefiore
    "330059": "Montefiore", "330086": "Montefiore", "330184": "Montefiore", "330104": "Montefiore",
    "330304": "Montefiore", "330264": "Montefiore",
    # NYC Health + Hospitals
    "330204": "NYC Health + Hospitals", "330128": "NYC Health + Hospitals", "330240": "NYC Health + Hospitals",
    "330127": "NYC Health + Hospitals", "330202": "NYC Health + Hospitals", "330080": "NYC Health + Hospitals",
    "330199": "NYC Health + Hospitals", "330196": "NYC Health + Hospitals", "330231": "NYC Health + Hospitals",
    "330396": "NYC Health + Hospitals",
    # One Brooklyn Health
    "330233": "One Brooklyn Health",
    # SBH
    "330399": "SBH Health System",
    # Catholic Health (Long Island)
    "330286": "Catholic Health (Long Island)", "330182": "Catholic Health (Long Island)",
    "330259": "Catholic Health (Long Island)", "330401": "Catholic Health (Long Island)", "330332": "Catholic Health (Long Island)",
    # Stony Brook
    "330393": "Stony Brook Medicine",
    # Rochester Regional
    "330125": "Rochester Regional Health", "330226": "Rochester Regional Health", "330030": "Rochester Regional Health",
    "330265": "Rochester Regional Health", "330073": "Rochester Regional Health", "330197": "Rochester Regional Health",
    "331322": "Rochester Regional Health", "331315": "Rochester Regional Health",
    # UR Medicine
    "330285": "UR Medicine", "330164": "UR Medicine", "330074": "UR Medicine", "330096": "UR Medicine",
    "330238": "UR Medicine", "330151": "UR Medicine", "330058": "UR Medicine", "331314": "UR Medicine",
    # Albany Med
    "330013": "Albany Med Health System", "330222": "Albany Med Health System", "330094": "Albany Med Health System", "330191": "Albany Med Health System",
    # Ellis
    "330153": "Ellis Medicine",
    # Bassett
    "330136": "Bassett Healthcare Network", "330085": "Bassett Healthcare Network", "331305": "Bassett Healthcare Network",
    "331320": "Bassett Healthcare Network", "331311": "Bassett Healthcare Network",
    # UHS
    "330394": "United Health Services", "330033": "United Health Services", "331312": "United Health Services",
    # Kaleida (330103 Olean, 330111 Bertrand Chaffee = passive-parent)
    "330005": "Kaleida Health", "330103": "Kaleida Health", "330111": "Kaleida Health",
    # Catholic Health (Buffalo/WNY)
    "330279": "Catholic Health (Buffalo)", "330078": "Catholic Health (Buffalo)", "330102": "Catholic Health (Buffalo)", "330188": "Catholic Health (Buffalo)",
    # ECMC
    "330219": "Erie County Medical Center",
    # MVHS
    "330044": "Mohawk Valley Health System",
    # WMCHealth
    "330234": "WMCHealth", "330158": "WMCHealth", "330135": "WMCHealth", "330205": "WMCHealth", "330224": "WMCHealth", "331304": "WMCHealth",
    # Garnet
    "330126": "Garnet Health", "330386": "Garnet Health", "331303": "Garnet Health",
    # Arnot
    "330090": "Arnot Health", "330800": "Arnot Health",
    # Guthrie
    "330277": "Guthrie", "330175": "Guthrie",
    # Cayuga Health
    "330307": "Cayuga Health", "331313": "Cayuga Health",
    # St. Peter's Health Partners (Trinity)
    "330057": "St. Peter's Health Partners", "330180": "St. Peter's Health Partners", "330047": "St. Peter's Health Partners",
    # UVM Health Network (NY facilities)
    "330250": "University of Vermont Health Network", "331321": "University of Vermont Health Network",
    # SUNY
    "330241": "SUNY Upstate", "330350": "SUNY Downstate",
    # St. Joseph's Health (Trinity, Syracuse)
    "330140": "St. Joseph's Health (Trinity)",
}


def main() -> int:
    hospitals = []
    for ccn, h in sorted(CMS_BY.items()):
        if h["hospital_type"] not in CONSUMER:
            continue
        if ccn in DISPOSED:
            continue
        region = resolve_region(TAX, h["countyparish"], h["citytown"])
        hospitals.append({
            "ccn": ccn,
            "name": h["facility_name"].title().replace("  ", " ").strip(),
            "address": h["address"].title() if h.get("address") else "",
            "city": h["citytown"].title(),
            "zip": h["zip_code"],
            "county": h["countyparish"].title(),
            "type": h["hospital_type"],
            "system": SYSTEM_MAP.get(ccn, ""),
            "region": region,
            "source": "cms",
        })
    for a in ADDITIONS:
        region = resolve_region(TAX, a["county"], a["city"])
        rec = {
            "ccn": a["ccn"], "name": a["name"], "address": a.get("address", ""),
            "city": a["city"], "zip": a["zip"],
            "county": a["county"].title(), "type": a["type"], "system": a.get("system", ""),
            "region": region, "source": "nysdoh",
        }
        if a.get("ccn_confidence"):
            rec["ccn_confidence"] = a["ccn_confidence"]
        hospitals.append(rec)
    hospitals.sort(key=lambda r: r["ccn"])

    seed = {
        "_meta": {
            "description": (
                "Authoritative New York operating general acute-care + critical-access + rural-emergency "
                "hospital identity for the Carevero NY foundation. Reconciled from CMS Hospital General "
                "Information (data.cms.gov dataset xubh-q36u, state=NY, retrieved 2026-08-23) UNION the "
                "operating hospitals CMS Care Compare omits (confirmed in NYSDOH Health Facility General "
                "Information, health.data.ny.gov dataset vn5v-hh5r) MINUS closed/merged/superseded/specialty/"
                "rehab-LTAC dispositions. Federal (VA/DoD), Psychiatric, and Childrens CMS rows are excluded "
                "by type. Region is derived from CMS/NYSDOH county via ny_region_taxonomy.json (NYC counties "
                "-> boroughs). IDENTITY only — no pricing; MRF ingestion is a later step. NH and MA baselines "
                "are not affected. Multi-campus single-CCN hospitals are one seed facility (see multi_campus_single_ccn)."
            ),
            "retrieval_date": "2026-08-23",
            "region_taxonomy": TAX["_meta"]["regions"],
            "counts": {
                "cms_consumer_type": sum(1 for h in CMS_BY.values() if h["hospital_type"] in CONSUMER),
                "operating_denominator": len(hospitals),
                "from_cms": sum(1 for h in hospitals if h["source"] == "cms"),
                "added_from_nysdoh": len(ADDITIONS),
            },
            "excluded_closed": DISPO_CLOSED,
            "excluded_merged": DISPO_MERGED,
            "excluded_superseded": DISPO_SUPERSEDED,
            "specialty_bucket": DISPO_SPECIALTY,
            "excluded_rehab_ltac": DISPO_REHAB_LTAC,
            "excluded_by_type": {
                "federal_va_dod": sum(1 for h in CMS_BY.values() if h["hospital_type"] in ("Acute Care - Veterans Administration", "Acute Care - Department of Defense")),
                "psychiatric": sum(1 for h in CMS_BY.values() if h["hospital_type"] == "Psychiatric"),
                "childrens": sum(1 for h in CMS_BY.values() if h["hospital_type"] == "Childrens"),
            },
            "added_from_nysdoh": [
                {"ccn": a["ccn"], "name": a["name"], "city": a["city"], "county": a["county"].title(),
                 "reason": "operating general-acute hospital omitted from CMS Care Compare (xubh-q36u); confirmed operating in NYSDOH vn5v-hh5r"}
                for a in ADDITIONS
            ],
            "multi_campus_single_ccn": [
                {"ccn": "330101", "note": "NYP: Weill Cornell + Columbia/CUIMC + Allen + Morgan Stanley/Komansky Children's"},
                {"ccn": "330214", "note": "NYU Langone Hospitals: Tisch + Kimmel Pavilion + Hassenfeld Children's + NYU Orthopedic"},
                {"ccn": "330024", "note": "Mount Sinai Hospital + Mount Sinai Queens (subunit)"},
                {"ccn": "330059", "note": "Montefiore: Moses + Weiler/Einstein + Children's Hospital at Montefiore (CHAM)"},
                {"ccn": "330160", "note": "Staten Island University Hospital: North + South campuses"},
                {"ccn": "330005", "note": "Kaleida Health: Buffalo General + Gates Vascular + Millard Fillmore Suburban + Oishei Children's"},
                {"ccn": "330078", "note": "Sisters of Charity: Main St (Buffalo) + St. Joseph Campus (Cheektowaga)"},
                {"ccn": "330153", "note": "Ellis Hospital + Bellevue Woman's Center (Niskayuna)"},
                {"ccn": "330286", "note": "Good Samaritan University Hospital (West Islip) + St. Charles Campus (Port Jefferson, ex-330246)"},
                {"ccn": "330264", "note": "Montefiore St. Luke's Cornwall: Newburgh (inpatient) + Cornwall (ambulatory)"},
                {"ccn": "330073", "note": "United Memorial Medical Center (Batavia): North St + Bank St campuses"},
                {"ccn": "330394", "note": "UHS: Wilson Medical Center (Johnson City) + Binghamton General"},
                {"ccn": "330224", "note": "HealthAlliance Hospital (Kingston): Mary's Ave + Broadway campuses"},
                {"ccn": "330127", "note": "Jacobi shares NYS opcert 7000002H with North Central Bronx (NCB has no separate CCN)"},
                {"ccn": "330188", "note": "Mount St. Mary's + Lockport Memorial Hospital campus (replaced closed Eastern Niagara)"},
                {"ccn": "330234", "note": "Westchester Medical Center: main + Maria Fareri Children's + MidHudson Regional division"},
            ],
        },
        "hospitals": hospitals,
    }
    out = DATA / "ny_hospitals_seed.json"
    out.write_text(json.dumps(seed, indent=1, ensure_ascii=False) + "\n")

    from collections import Counter
    dist = Counter(h["region"] for h in hospitals)
    print(f"Wrote {out} — {len(hospitals)} operating hospitals ({seed['_meta']['counts']['from_cms']} CMS + {len(ADDITIONS)} NYSDOH)")
    print(f"Systems assigned: {sum(1 for h in hospitals if h['system'])}/{len(hospitals)}")
    print("Region distribution:")
    for r in TAX["_meta"]["regions"]:
        print(f"  {dist.get(r,0):3d}  {r}")
    none_region = [h['ccn'] for h in hospitals if h['region'] is None]
    print(f"Hospitals with unresolved region: {none_region if none_region else 'NONE'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
