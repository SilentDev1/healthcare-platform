# Hospital price source discovery

Discovery begins with the reviewed official-domain map, checks `/cms-hpt.txt`, and prefers direct declarations over HTML inspection. If no declaration exists, the collector scans only same-site price-transparency links with bounded redirects. Every success, absence, redirect, and failure creates a discovery observation.

Run `make discover-hospital-price-sources`. A manual association adds a new reviewed source; it must not delete prior observations. HTTP-only sources, stale sources, third-party redirects, and unsupported layouts require review.
