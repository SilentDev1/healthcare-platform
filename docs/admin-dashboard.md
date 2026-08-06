# Admin dashboard

Phase 3 adds internal-only views for ranked search testing, the procedure catalog, facility
identity governance, read-only identity candidates, data-health evaluations, pipeline status,
and search-index operations. Pages fetch the FastAPI service and show explicit empty/error
states; no production mock data or browser-side embedded healthcare records are used. Candidate
approval remains intentionally read-only until an authenticated reviewed workflow is available.

The admin Next.js application reads FastAPI on `CARECOMPARE_API_URL` and provides dashboard,
facility, import, source-file, unmatched-record, and quality-measure pages. Start the API and
run `make admin`; open <http://localhost:3001>.

Pages use server-side fetching with no production mock data. They include route loading UI,
explicit empty states, accessible table headings/captions, and visible API error states. The
dashboard reports facility counts, import health, unmatched records, source freshness, and
quality coverage. There are no mutation or authentication endpoints in Phase 2.
