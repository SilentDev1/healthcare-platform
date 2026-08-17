# NH Missing-Pricing Acquisition Matrix

Source: production API (authority). Total **148** locations · **26** priced · **122** unpriced (122 to investigate).

## Coverage by capability (priced / total)

| Capability | Priced | Total |
|---|---:|---:|
| urgent_care | 0 | 39 |
| physical_therapy | 0 | 33 |
| hospital | 26 | 28 |
| emergency_department | 26 | 26 |
| laboratory | 0 | 24 |
| ambulatory_surgery | 0 | 10 |
| imaging | 0 | 10 |
| rehabilitation | 0 | 4 |
| chiropractic | 0 | 3 |

_Note: locations may hold multiple capabilities, so capability totals do NOT sum to unique locations._

## Unpriced organizations (34), most locations first

Organization-first: one verified public source may cover many locations. Each org gets a documented disposition before being declared unpriced.

| # | Organization | Type | Locs | Capabilities | Cities |
|---:|---|---|---:|---|---|
| 1 | ConvenientMD | urgent_care | 15 | urgent_care | Bedford, Belmont, Concord, Dover, Keene, Littleton, Londonderry, Manchester, Mer |
| 2 | Quest Diagnostics | independent_lab | 14 | laboratory | Amherst, Bedford, Claremont, Concord, Derry, Dover, Gilford, Goffstown, Londonde |
| 3 | ClearChoiceMD | urgent_care | 11 | urgent_care | Alton, Epping, Gilford, Goffstown, Hooksett, Lebanon, Nashua, Plaistow, Rocheste |
| 4 | Laboratory Corporation of America | independent_lab | 10 | laboratory | Bedford, Derry, Dover, Exeter, Portsmouth, Raymond, Rochester, Salem, Windham |
| 5 | Derry Imaging | imaging_center | 7 | imaging | Bedford, Concord, Derry, Dover, Londonderry, Raymond, Windham |
| 6 | Northeast Rehabilitation Hospital Network | rehabilitation | 7 | physical_therapy, rehabilitation | Manchester, Nashua, Plaistow, Portsmouth, Salem, Windham |
| 7 | Wentworth-Douglass Hospital | health_system | 7 | physical_therapy, urgent_care | Dover, Durham, Lee, Portsmouth, Somersworth |
| 8 | Apple Therapy Services | physical_therapy | 6 | physical_therapy | Amherst, Bedford, Londonderry, Manchester, Nashua |
| 9 | Access Sports Medicine & Orthopaedics | ambulatory_surgery_center | 4 | ambulatory_surgery, physical_therapy | Auburn, Dover, Exeter, Portsmouth |
| 10 | Granite State Physical Therapy | physical_therapy | 4 | physical_therapy | Concord, Gilford, Hooksett, Plymouth |
| 11 | Professional Physical Therapy | physical_therapy | 4 | physical_therapy | Epping, Seabrook, Somersworth, Stratham |
| 12 | Concentra | urgent_care | 3 | urgent_care | Concord, Manchester, Nashua |
| 13 | Elliot Health System | health_system | 3 | urgent_care | Bedford, Londonderry, Manchester |
| 14 | The Joint Chiropractic | chiropractic | 3 | chiropractic | Manchester, Nashua, Salem |
| 15 | Bedford Ambulatory Surgical Center | ambulatory_surgery_center | 2 | ambulatory_surgery, imaging | Bedford |
| 16 | Cioffredi & Associates | physical_therapy | 2 | physical_therapy | Grantham, Lebanon |
| 17 | Dartmouth Health | health_system | 2 | physical_therapy | Lebanon |
| 18 | Southern NH Health | health_system | 2 | urgent_care | Nashua |
| 19 | AFC Urgent Care | urgent_care | 1 | urgent_care | Hudson |
| 20 | Concord Hospital | health_system | 1 | urgent_care | Concord |
| 21 | HAMPSTEAD HOSPITAL & RESIDENTIAL TREATMENT FACILIT | hospital_system | 1 | hospital | HAMPSTEAD |
| 22 | Minimally Invasive Surgery Center of New England | ambulatory_surgery_center | 1 | ambulatory_surgery | Bedford |
| 23 | MinuteClinic | urgent_care | 1 | urgent_care | Nashua |
| 24 | NEW HAMPSHIRE HOSPITAL | hospital_system | 1 | hospital | CONCORD |
| 25 | Nashua Ambulatory Surgical Center | ambulatory_surgery_center | 1 | ambulatory_surgery | Nashua |
| 26 | New Hampshire Open MRI | imaging_center | 1 | imaging | West Lebanon |
| 27 | North Atlantic Surgical Suites | ambulatory_surgery_center | 1 | ambulatory_surgery | Salem |
| 28 | Northridge Surgical Suites | ambulatory_surgery_center | 1 | ambulatory_surgery | Nashua |
| 29 | Novamed Surgery Center of Nashua | ambulatory_surgery_center | 1 | ambulatory_surgery | Nashua |
| 30 | Orthopaedic Surgery Center | ambulatory_surgery_center | 1 | ambulatory_surgery | Concord |
| 31 | Performance Health NH | physical_therapy | 1 | physical_therapy | Concord |
| 32 | Portsmouth Surgery Center | ambulatory_surgery_center | 1 | ambulatory_surgery | Seabrook |
| 33 | Shields Health Care Group | imaging_center | 1 | imaging | Portsmouth |
| 34 | Surgical Center of New Hampshire at Derry | ambulatory_surgery_center | 1 | ambulatory_surgery | Derry |

Full per-location detail + research disposition: `data/nh_pricing_acquisition_ledger.json`.
