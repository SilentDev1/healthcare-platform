# Procedure catalog

The seed contains 13 categories and 50 independently written consumer service labels. Run
`make seed-procedure-catalog`; repeated runs are idempotent. Add a procedure with a unique slug,
plain-language descriptions, category, setting, related aliases, and an explicit review.

Consumer descriptions and billing-code mappings are separate. A code mapping defaults to
`draft`; approval requires evidence, version review, and licensing review. A code does not imply
a complete episode, so bundles enumerate optional and required components explicitly.
