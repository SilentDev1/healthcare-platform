# Hospital price importer

Run the offline end-to-end workflow with `make pricing-pipeline`. Live work is deliberately separate: discover, review coverage, run `make download-hospital-price-files`, then `make import-hospital-prices`.

Downloads are streamed with byte, timeout, redirect, content-type, and decompression limits. ZIP paths are validated against traversal and expanded-size limits. Parsers inspect a bounded sample and stream rows. Accepted rows use `Decimal`, retain raw payload hashes and source identifiers, and reference the source file and import run. Negative and nonnumeric prices are rejected without changing the source file. Add a parser by registering deterministic detection, streaming iteration, normalization, fixture coverage, and a version bump.
