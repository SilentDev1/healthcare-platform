# Hospital price schema

`facility_price_sources` and discovery tables track source history. `hospital_price_records` stores the service-level fields; payer/plan rates remain separate in `hospital_price_rate_details`; all monetary columns are fixed-precision Numeric. Codes, candidates, reviewed mappings, anomalies, and unmatched rows are independent records so source facts are not overwritten by later review.

Consumer projections are `facility_procedure_price_observations` and summaries. They separate setting, payer, plan, and component scope. Raw rows are not consumer totals: a line item may exclude professional, anesthesia, pathology, medication, implant, or other charges.
