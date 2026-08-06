# Admin dashboard

The admin Next.js application reads FastAPI on `CARECOMPARE_API_URL` and provides dashboard,
facility, import, source-file, unmatched-record, and quality-measure pages. Start the API and
run `make admin`; open <http://localhost:3001>.

Pages use server-side fetching with no production mock data. They include route loading UI,
explicit empty states, accessible table headings/captions, and visible API error states. The
dashboard reports facility counts, import health, unmatched records, source freshness, and
quality coverage. There are no mutation or authentication endpoints in Phase 2.
