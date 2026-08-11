# Carevero private beta readiness checklist

Completed: 2026-08-10

## Release gate

- [x] PostgreSQL 17 healthy and migration head `0009`
- [x] No active imports during QA
- [x] Anonymous homepage → search → results → compare journey works
- [x] Everyday-language search works for MRI, knee scan, CAT scan, CT,
      colonoscopy, mammogram, blood test, childbirth, and C-section concepts
- [x] ZIP/city validation and useful no-result recovery are present
- [x] Cash and negotiated prices are labeled without implying a final bill
- [x] Selected payer context survives into comparison
- [x] Three-item anonymous comparison state is procedure-scoped and shareable
- [x] Multi-location identities remain distinct in result and facility views
- [x] Facilities with no public price data remain visible with honest empty states
- [x] Source, freshness, official URL, and CMS quality attribution are visible
- [x] Fixture sources are excluded from public coverage and price views
- [x] Verified phone and official website actions only; no fabricated booking
- [x] Branded loading, empty, error, and 404 experiences
- [x] Keyboard-operable native controls, visible labels, skip link, status/alert semantics
- [x] Responsive QA at 375/390/430 mobile widths and desktop layouts
- [x] Core routes have appropriate metadata; search and compare are `noindex`
- [x] Sitemap contains useful core, facility, and procedure URLs only
- [x] Python test, lint, formatting, and strict type-check pass
- [x] TypeScript test, lint, formatting, and type-check pass
- [x] Public and admin production builds pass
- [x] Dependency audit reports zero vulnerabilities
- [x] Production-mode browser smoke passes
- [x] No account wall, mock production price, PHI, AI, insurer TiC, ad, payment,
      deployment, or commercial infrastructure introduced

## Private-beta test script

1. On a phone-sized viewport, open Carevero and confirm it states that use is free
   and requires no account.
2. Search “knee scan” near Manchester and open the MRI knee price results.
3. Clear or change the location and confirm the result context changes visibly.
4. Filter a procedure by Medicare and add two facilities to comparison.
5. Confirm the compare page says Medicare and labels the negotiated range as the
   selected-payer range.
6. Share/copy the comparison URL, open it in another tab, and confirm the same
   procedure, facilities, and payer context appear.
7. Open a priced hospital and confirm procedures are grouped by physical location,
   with source dates and official source links.
8. Open a hospital without public prices and confirm the page does not invent a
   price but still shows available CMS quality and verified contact actions.
9. Open the map and verify markers/list entries distinguish public-price coverage.
10. Read About the data and How it works; report any wording that could imply a
    guaranteed bill, insurer coverage, or medical recommendation.

Beta testers should not submit medical records, diagnoses, member IDs, or other
sensitive health information in feedback.

## Exit criteria

Private beta may begin when the beta environment is prepared separately, the
release commit is deployed through the approved process, and a non-PHI feedback
channel and owner are named. Any new P0/P1 finding blocks expansion until fixed.
