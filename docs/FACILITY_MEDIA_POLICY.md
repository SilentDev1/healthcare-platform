# Carevero Facility Media Policy

State-neutral policy for hospital / service-location imagery. Applies to every
facility Carevero shows (NH today, MA and nationwide later). The governing
product rule is the same one that applies to prices: **never mislead the user.**
An image must depict the real facility, its license must permit our use, and its
provenance must be recorded. When in doubt, we show the neutral placeholder.

## 1. Permitted sources (`facility_media.source_type`)

In rough order of preference:

1. `official_hospital` / `media_kit` — imagery provided by the hospital or health
   system for public use (press/media kits, explicit permission).
2. `official_website` — assets from the hospital's official website **only when
   usage terms permit** reuse. Public accessibility is *not* permission.
3. `government_public_domain` — U.S. federal/state public-domain imagery.
4. `wikimedia` — Wikimedia Commons (and equivalent repositories) files under a
   free license: `CC0`, public domain, `CC BY`, or `CC BY-SA`. Attribution is
   mandatory for CC BY / CC BY-SA and is rendered on the image (see §5).
5. `admin_upload` — imagery a Carevero administrator has the right to publish and
   has reviewed.

## 2. Prohibited sources

- Google Images / arbitrary web scraping.
- Any image chosen only because it "looks like a hospital".
- `All rights reserved` / unlicensed / unknown-license imagery.
- Social-media photos without an explicit free license and identity confirmation.
- Stock photography used as though it depicts a specific real facility.
- Any image whose license or usage basis cannot be reasonably established — it is
  **not** ingested as verified; at most it is recorded as `pending` for review.

## 3. Provenance requirements (recorded on every row)

- `source_url` — where the asset came from (the Commons file page / official page).
- `source_type`, `source_name` — provenance category and human-readable origin.
- `license_type`, `license_url` — the specific license (e.g. `CC BY-SA 4.0`).
- `attribution_text`, `copyright_owner` — for attribution-required licenses.
- `checksum_sha256`, `width`, `height`, `mime_type`, `file_size` — from validation.

A row missing a license basis **must not** be `verified`.

## 4. Verification lifecycle (`facility_media.verification_status`)

- `pending` — discovered or uploaded; **never shown publicly**.
- `verified` — a human reviewer confirmed (a) the license permits Carevero's use
  and (b) the image genuinely depicts the correct facility / service location.
  Only `verified` media is eligible to be a public primary image.
- `rejected` — reviewed and unusable (wrong building, licensing, quality).
- `broken` — a previously-usable asset later failed retrieval/validation; it
  falls back automatically.

Automated discovery **never** auto-publishes. Discovery produces `pending`
candidates; publication requires review. This mirrors the pricing rule that
mappings are reviewed, never fuzzy-published.

## 5. Attribution

For CC BY / CC BY-SA, the required credit (author + license) is stored in
`attribution_text` and rendered as a visible caption on the image
(`FacilityImage` credit overlay) and localized as "Photo: {source}" where a
short source label is more appropriate. Public-domain / CC0 imagery may omit a
visible credit but still records provenance.

## 6. Facility-location safety

`facility_media.service_location_id` distinguishes a photo of a specific physical
service location from a facility-wide/health-system photo. The selection layer
(`services/api/app/facility_media.py`) prefers a verified exact-location photo,
then a verified facility-level photo, then the placeholder. Carevero never shows
one location's building for a different physical location; if only a health-system
or main-campus photo exists and the card represents a different site, the neutral
placeholder is shown instead.

## 7. Replacement / removal

- Broken/invalid assets are marked `broken` and fall back automatically; they are
  re-checked (`last_checked_at`) and replaced when a valid asset is available.
- A takedown or licensing change → set `rejected` (or delete the row); the
  facility immediately reverts to the placeholder. No page ever breaks because an
  image is missing.

## 8. Fallback (deterministic)

```
verified service-location photo
  -> verified facility photo
    -> verified facility logo (media_type="logo")
      -> (future) verified health-system image, only if it does not misrepresent
        -> Carevero neutral placeholder (building glyph + initials)
```

A real **photo** always outranks a **logo** (`facility_media._rank`): a verified
logo is only shown when no verified photo exists, before the placeholder. Logos
are identification imagery (nominative use) from an official hospital/health-system
source; they go through the same verification gate as photos and record
provenance. Never scrape or apply a trademarked logo without review.

The placeholder is always a safe terminal state and is never a broken-image icon.

## 9. Storage

When licensing permits copying, verified imagery is copied into a
Carevero-controlled GCS bucket (`facility_media_bucket`) and served from
`facility_media_public_base_url`, decoupling Carevero from external URL churn and
enabling normalized variants (thumbnail / card / detail). Until then, a verified
free-licensed asset may be remote-referenced by `cdn_url`/`source_url` with
attribution. Reasonable size/resolution limits are enforced at validation time to
avoid uncontrolled storage/egress cost.

## 10. Scale (NH → MA → nationwide)

Nothing in this policy or the schema is NH-specific. Identity is by `facility_id`
(+ optional `service_location_id`), never by state. The same discovery →
validate → review → publish pipeline serves every future state.
