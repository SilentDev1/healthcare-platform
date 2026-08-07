# Pricing performance

The downloader and parsers stream content, archive expansion is bounded, inserts use a configurable batch size (default 500), and canonical payer/code maps are cached per import. Query indexes cover source, facility, procedure, payer, publication state, and review queues.

Benchmark a small fixture, a larger representative source within configured limits, the procedure list API, summary query, anomaly list, and payer/plan filters. Record rows per second, parse and summary time, batch size, and approximate peak RSS. Do not raise limits automatically for an oversized live file.
