# PROPERTY REGISTER — the Slipstream family (compiled at the Day-120 close)

Compiled by Claude on 2026-11-17 from packet 121. The sources are `cp-ref-places-master-list.md` (each place's own row), `cp-ref-bank-balances.md` and `cp-campaign-state-day-120.md` §10.
- **Cost basis** is the recorded purchase price: the deed, closing or founding figure as the page states it. It is never a market value.
- **"—"** means the page records the property as owned but states no price. These properties are listed but left out of the totals.
- **Status values:** **Owned** (deeded, recorded or delivered) · **Committed** (won or accepted, not yet deeded; the cost is shown but not added to owned property) · **Verify** (the ownership or price reading needs Shane's confirmation).
- **Updating it.** This file is read by `tools/bank-to-ledger.py`. Add or change a row when a close deeds, sells or prices a property. When a packet carries its own `cp-ref-property-register.md`, the tool uses that one instead.

| Property | Owner | District | Status | Cost basis | Source |
|---|---|---|---|---:|---|
| Corvane Tower (41 fl, ~620,000 sq ft) | Slipstream Industries | The Glen | Owned | 189,800,000.00 | deed 12:10 Day 120 (196,000,000.00 less the 6,200,000.00 report credit) |
| Mercy Ridge General Hospital, 4100 Arcadia Dr | Slipstream Medical Complex | New Westbrook | Owned | 52,000,000.00 | recorded 15:18 Day 102 |
| The Cormorant (SIVOSS HQ, 14 fl hotel) | Slipstream Industries | Heywood | Owned | 26,500,000.00 | recorded 15:51 Day 102 |
| The New Westbrook tower (12 fl, 280 apts) | Slipstream Industries | New Westbrook | Owned | 10,000,000.00 | deed Fri Oct 20, booked Day 119 |
| New Westbrook parcels A+B (cube hotel + container yard, 4.0 ac) | Slipstream Industries | New Westbrook | Owned | 7,310,000.00 | booked Day 119 |
| Hawser Lane (84,000 sq ft, 4.0 ac) | Slipstream Industries | Heywood Industrial Zone | Owned | 4,900,000.00 | closed 11:02 Day 92 |
| New Westbrook parcel D (6 conapt houses, 1.8 ac) | Slipstream Industries | New Westbrook | Owned | 3,570,000.00 | booked Day 119 |
| Nightshades (the Brasserie Kroll building) | NorTex Holdings | Little Europe | Owned | 3,050,000.00 | title vested Day 72 |
| 1180 Ropewalk Lane (68,000 sq ft warehouse) | IntraCorp Logistics | Heywood Docks | Owned | 2,800,000.00 | deed Day 81 (+36,900.00 closing costs) |
| LB-OC-4000 (4,000 acres) | NorTex Exploration | Beyond the Outskirts | Owned | 2,200,000.00 | closed 10:02 Day 102 |
| LB-TF-0640, the Laguna Bend farm (640 ac) | NorTex Agriculture | Outskirts | Owned | 1,800,000.00 | recorded 09:00 Day 108 |
| OSK-CH-34S, Zakrajšek's truck stop (85 ac) | IntraCorp Logistics | Outskirts | Owned | 1,300,000.00 | closed 12:09 Day 99 |
| New Westbrook lot C (tax-forfeit lot, 1.1 ac) | Slipstream Industries | New Westbrook | Owned | 950,000.00 | booked Day 119 |
| Five Mile — the land under the water tower | Hakk (personal) | Outskirts (~mile 186) | Owned | 100,000.00 | Day 108 (G3) |
| P01 the Voinea Building, 88 Halcyon Plaza | Aster Vale Holdings | City Center | Owned | 4,800,000.00 | founding value (2023) |
| P11 the Ignac Compound, 6 Arroyo Vista Rd | Aster Vale Holdings | Rancho Coronado | Owned | 4,600,000.00 | founding value (2023) |
| P05 the Schmidt Building, 310 Devereaux Sq | Aster Vale Holdings | Little Europe | Owned | 4,100,000.00 | founding value (2023); SI leases floors 6–8 |
| P10 Firgantoro Distribution Center, 820 Junction Market Rd | Aster Vale Holdings | Heywood | Owned | 4,000,000.00 | founding value (2023) |
| P06 Eigenwillig Transport Yard, 1900 Harbor Transit Rd | Aster Vale Holdings | South Night City | Owned | 3,700,000.00 | founding value (2023) |
| P04 the Montemayor, 27 Bellweather Terrace | Aster Vale Holdings | Upper Marina | Owned | 3,400,000.00 | founding value (2023) |
| P02 Hrynkiewicz Freight Yard, 1448 Sutter Freight Way | Aster Vale Holdings | Watson | Owned | 3,200,000.00 | founding value (2023) |
| P08 the Cordoba Medical Building, 114 St. Elmo Ave | Aster Vale Holdings | Little Europe | Owned | 3,100,000.00 | founding value (2023) |
| P03 the Purmals Compound, 6021 Foundry Ave | Aster Vale Holdings | Heywood | Owned | 2,900,000.00 | founding value (2023) |
| P09 Prabowo Records Center, 442 Wycliffe St | Aster Vale Holdings | Watson | Owned | 2,600,000.00 | founding value (2023) |
| P07 12 Larkspur Rise (Estate M) | Hakk (personal) | Executive Zone | Owned | — | Aster Vale P07 "Hakk's"; no price on the page |
| WTS Security Complex, 1410 Parkside Blvd | Whitehat Technical Services | The Glen | Owned | — | delivered Day 97; the 50,000,000.00 1stNC facility paid off |
| The Ashford, 40th floor | Whitehat Technical Services | Charter Hill | Owned | — | title recorded Day 64 |
| Arboleda Pallet & Crate lot (1.1 ac) | NorTex Holdings | Heywood Industrial Zone | Owned | — | closed Day 78 in the three-parcel NorTex package |
| WTS Data Services building (the former shell) | NorTex Holdings | Heywood Industrial Zone | Owned | — | closed Day 78 with the block |
| Seamwright Technical Textiles building (14,000 sq ft) | Aster Vale Holdings | — | Verify | 1,700,000.00 | Day 101: "the building to Aster Vale at 1,700,000.00 (SI capitalizes)"; closing not seen |
| Ironweave Ballistic Textiles building (19,000 sq ft) | SI TEAB | — | Verify | — | Day 101: in the 7,200,000.00 Ironweave deal (business + building) |
| HZ-NE-0417, the Crater | Slipstream Industries | The Hot Zone | Committed | 500,000,000.00 | won Day 109; 420,000.00 deposit paid; 499,580,000.00 due at transfer after the clearance certificate (due Tue Dec 12); not deeded |
| Fernhill, 2240 Kettle Road | SI Community Development | — | Committed | — | accepted 22:31 Day 114; close by Fri Nov 3 |
