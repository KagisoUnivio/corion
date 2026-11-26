# Market data quality report

Source file `market_data.sql`. Line numbers refer to the source export.

| Table | Source INSERTs | SQLite rows | Excluded |
| --- | ---: | ---: | ---: |
| Instruments | 20 | 20 | 0 |
| DailyPrices | 620 | 616 | 4 |

## Record-level findings

| Source line | Action | Details |
| ---: | --- | --- |
| 61 | Repaired | Instrument 20: escaped the apostrophe in `Karoo Winemakers' Co-op`. |
| 110 | Excluded | Price for instrument 2 on 2026-10-20 duplicates line 109 exactly. |
| 155 | Superseded | Instrument 3 on 2026-11-06: replaced close 32634.000000 with 33646.000000 from line 156, labeled `JSE EOD (corrected)`. |
| 221 | Retained as NULL | NMR (instrument 5) on 2026-11-09 has a missing close. |
| 222 | Retained as NULL | NMR (instrument 5) on 2026-11-10 has a missing close. |
| 223 | Retained as NULL | NMR (instrument 5) on 2026-11-11 has a missing close. |
| 224 | Retained as NULL | NMR (instrument 5) on 2026-11-12 has a missing close. |
| 225 | Retained as NULL | NMR (instrument 5) on 2026-11-13 has a missing close. |
| 529 | Excluded | Price for instrument 15 on 2026-10-20 duplicates line 528 exactly. |
| 684 | Excluded | DailyPrices: truncated final INSERT (ClosePrice has an invalid or unfinished value). Source values: `20, CAST(N'2026-11-13' AS Date), CAST(4535` |

## Conversion and checks

- Rebuilt both tables and primary keys in SQLite, bypassing SQL Server directives and storage options. Added a foreign key from prices to instruments.
- Stored dates as ISO text and decimals in SQLite NUMERIC columns, which can use floating-point storage. Kept each instrument's original quote unit.
- Checked metadata completeness, duplicate codes by exchange, contract sizes, date validity, weekend dates, weekday gaps within each instrument's observed range, missing sources and closes, non-positive prices, accrued interest by asset class, and moves of 20% or more between adjacent observations. The weekday check uses weekdays without an exchange holiday calendar.
- Verified row counts, database integrity and foreign keys. Loaded the generated SQL into a fresh SQLite database and compared its rows to the generated database.
