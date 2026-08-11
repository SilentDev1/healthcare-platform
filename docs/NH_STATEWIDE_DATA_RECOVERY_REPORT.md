# New Hampshire Statewide Data Recovery Report

## Executive Summary

Phase 4.7 traced the public-coverage funnel without substituting fixtures or
redownloading every source. It repaired physical-location association, fixture
publication safeguards, raw-to-normalized monetary auditing, source discovery for
major health systems, importer failure durability, and official modifier storage. A
bounded Cloud Run recovery sequence then targeted only verified zero/limited hospitals.
Final production counts are recorded in **After Coverage** after the serial recovery
waves and safety audit complete.

## Before Coverage

The frozen live baseline had 26 active NH consumer hospitals, approximately 11 with at
least one public procedure and 15 with zero public procedures. Production contained
about 1,729,684 normalized price records and 7,077 summaries at migration 0008. The
pre-recovery repair audit subsequently measured 13/26 hospitals with public procedures,
13 zero, 2 limited, and 11 with meaningful procedure coverage.

## Statewide Publication Funnel

The audit now reports, per facility, verified sources, downloaded files, import runs,
normalized rows, missing physical locations, standard-coded rows, reviewed mappings,
publishable observations, official summaries, procedure counts, monetary coverage,
parser distribution, and the first exact blocker. This distinguishes a missing source
from a parser, location, mapping, publication, or summary failure.

## Fifteen Zero-Hospital Root Causes

The cohort was not one failure class. Root causes included unregistered current official
sources, stale/non-monetary historical files, physical-location identity loss, local or
proprietary code systems without reviewed mappings, and data present in normalized rows
but absent from public projections. The report never treats zero public prices as proof
that a hospital does not offer a service.

## Systemic Regression Analysis

The major systemic regression was source-to-physical-location association. Projection
identity correctly requires a location, but historical records could lose that link when
active source schedules overlapped. Association now evaluates active verified sources,
preserves distinct campuses and emergency locations, and avoids a misleading canonical
facility-only merge. Fixture sources are explicitly review-required and cannot enter
the public projection even if a test URL is later rewritten.

## Littleton Trace

Littleton's stored 2023 source contained 20,586 normalized records and mapped codes but
no monetary values, so no honest price could be published from it. Recovery uses the
current official source rather than fabricating values or relabeling gross/reference
fields.

## Laconia Trace

The repair linked 97,817 records to the verified Laconia physical location. Its remaining
zero state was then correctly attributed to mapping: most source rows used unknown/local
codes without approved public mappings. The process did not promote fuzzy candidates.

## Health-System Findings

### SolutionHealth

Elliot and Southern New Hampshire sources are independently registered to their
canonical facilities and physical locations. Shared system ownership does not merge
their data or identities.

### Dartmouth Health

Alice Peck Day, Cheshire, Mary Hitchcock, and New London have separate official source
URLs and CCNs. Cheshire's current source is a large compressed CSV with long official
modifier text; migration 0010 expands modifier storage to 255 characters rather than
truncating source truth.

### HCA

Portsmouth, Parkland, and Frisbie schedules preserve physical service locations.
Portsmouth/Dover/Seabrook and Parkland Derry/Plaistow remain distinct public locations,
while overlapping source schedules are provenance-preserving and do not create duplicate
public identity keys.

### Other Vendor Findings

Current verified sources were registered for Androscoggin Valley, Huggins, Littleton,
Monadnock, Speare, Valley Regional, and other regional hospitals. Format and archive
validation remain bounded; HTML/error payloads cannot be imported as price files.

## Recovered Hospitals

Final production list pending completion of the serial Dartmouth, regional, and Valley
recovery waves.

## Still-Zero Hospitals

Final production list and exact blocker pending the post-recovery statewide audit. A
remaining zero will be reported honestly; the phase has no numeric quota that authorizes
unsafe mappings.

## Procedure Coverage

Required live checks cover MRI knee, MRI brain, CT abdomen/pelvis, diagnostic mammogram,
colonoscopy, knee replacement, and hip replacement. Pre-recovery live facility coverage
was respectively 8, 11, 6, 6, 6, 8, and 8 of 26 active hospitals.

## Manchester, Nashua, and Lebanon/Dartmouth Coverage

CMC's Manchester source was independently traced and verified. Elliot, Southern New
Hampshire, Mary Hitchcock, Alice Peck Day, Cheshire, and New London use bounded official
source recovery. Final procedure counts are populated from the post-wave audit.

## Price Accuracy Audit

The price auditor now compares stored normalized amounts with bounded raw monetary fields
or rate payload values before falling back to parser projections. It records exact match,
deterministic transformation, provenance, and mismatch evidence. Final production sample
size and discrepancy count are populated after recovery; the required target is zero
unexplained monetary discrepancies.

## Insurance and Payer Findings

Raw payer and plan strings remain immutable. Deterministic aliases map only reviewed
identities; unknown payers/plans remain review-required. Published negotiated rates do
not establish acceptance, network participation, benefit coverage, or patient cost.

## NH HealthCost Feasibility

NH HealthCost may later provide a separate state claims/consumer context source, subject
to licensing, methodology, freshness, and service-identity review. It is not silently
mixed with hospital MRF rates in this phase, and insurer Transparency in Coverage
ingestion was not started.

## Consumer Status Model

Consumer status derives from official publishable summary coverage and transparent
blockers. Missing data remains visible and distinct from service unavailability. Raw
pipeline states and parser internals stay administrative.

## Deployment

Cloud Build and existing Cloud Run services/jobs are used; no production container is
built locally. Migrations are forward-only in production, infrastructure is reused, the
private-beta run.app hostname remains noindex, and DNS is unchanged.

## Safety Verification

Required invariants: zero public fixtures, zero negative public summaries, zero missing
summary provenance, zero unreviewed public mappings, zero duplicate public identity
keys, no AI-modified prices, one active NH write job at most, and no destructive facility
or location merges. Final results are populated after the last production audit.

## After Coverage

Pending completion of bounded serial recovery and final production audit.

## Remaining Blockers

Pending final classification. Expected legitimate classes include proprietary-only codes,
missing monetary fields, missing current official source, and source semantics unsafe to
publish without review.

## Recommended Next Phase

Maintain scheduled source freshness and resolve remaining hospitals by reviewed source
or mapping evidence. Do not begin insurer TiC ingestion, patient-specific estimates, or
AI pricing. Expand to Massachusetts only through the same state-neutral facility,
physical-location, procedure, payer/plan, source, and publication boundaries.
