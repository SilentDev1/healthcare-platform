# Pricing data health

Pricing health is separate from core facility identity and quality health. It measures discovery, download, parse success, mapping coverage, payer normalization, anomaly burden, freshness, and publishable coverage. Missing pricing does not invalidate facility identity.

Operators should review no-source, download failure, parsed-without-usable-records, stale, low-mapping, low-payer-normalization, high-anomaly, high-rejection, no-cash, and no-payer-rate conditions. Run `make evaluate-pricing-health` after imports and summary rebuilds.
